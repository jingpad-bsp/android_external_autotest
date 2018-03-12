# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Run a job against Autotest.

See http://goto.google.com/monitor_db_per_job_refactor

See also lucifer_run_job in
https://chromium.googlesource.com/chromiumos/infra/lucifer

job_reporter is a thin wrapper around lucifer_run_job and only updates the
Autotest database according to status events.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import atexit
import argparse
import logging
import os
import sys

from lucifer import autotest
from lucifer import eventlib
from lucifer import handlers
from lucifer import jobx
from lucifer import leasing
from lucifer import loglib

logger = logging.getLogger(__name__)


def main(argv):
    """Main function

    @param argv: command line args
    """
    print('job_reporter: Running with argv: %r' % argv, file=sys.stderr)
    args = _parse_args_and_configure_logging(argv[1:])
    logger.info('Running with parsed args: %r', args)
    with leasing.obtain_lease(_lease_path(args.jobdir, args.job_id)):
        autotest.monkeypatch()
        ret = _main(args)
    logger.info('Exiting normally with: %r', ret)
    return ret


def _parse_args_and_configure_logging(args):
    parser = argparse.ArgumentParser(prog='job_reporter', description=__doc__)
    loglib.add_logging_options(parser)

    # General configuration
    parser.add_argument('--jobdir', default='/usr/local/autotest/leases',
                        help='Path to job leases directory.')
    parser.add_argument('--run-job-path', default='/usr/bin/lucifer_run_job',
                        help='Path to lucifer_run_job binary')
    parser.add_argument('--watcher-path', default='/usr/bin/lucifer_watcher',
                        help='Path to lucifer_watcher binary')

    # Job specific

    # General
    parser.add_argument('--lucifer-level', required=True,
                        help='Lucifer level')
    parser.add_argument('--job-id', type=int, required=True,
                        help='Autotest Job ID')
    parser.add_argument('--results-dir', required=True,
                        help='Path to job results directory.')

    # STARTING flags
    parser.add_argument('--execution-tag', default=None,
                        help='Autotest execution tag.')

    # GATHERING flags
    parser.add_argument('--autoserv-exit', type=int, default=None, help='''
autoserv exit status.  If this is passed, then autoserv will not be run
as the caller has presumably already run it.
''')
    parser.add_argument('--need-gather', action='store_true',
                        help='Whether to gather logs'
                        ' (only with --lucifer-level GATHERING)')
    parser.add_argument('--num-tests-failed', type=int, default=-1,
                        help='Number of tests failed'
                        ' (only with --need-gather)')

    args = parser.parse_args(args)
    _validate_args(args)
    loglib.configure_logging_with_args(parser, args)
    return args


# TODO(crbug.com/810141): These options are optional to support
# GATHERING, so validation is done here rather than making them required
# during argument parsing.  Can be removed and the arguments made
# required after GATHERING is removed.
def _validate_args(args):
    if args.lucifer_level != 'STARTING':
        return
    if args.execution_tag is None:
        raise Exception('--execution-tag must be provided for STARTING')


def _main(args):
    """Main program body, running under a lease file.

    @param args: Namespace object containing parsed arguments
    """
    ts_mon_config = autotest.chromite_load('ts_mon_config')
    metrics = autotest.chromite_load('metrics')
    with ts_mon_config.SetupTsMonGlobalState(
            'job_reporter', short_lived=True):
        atexit.register(metrics.Flush)
        return _run_autotest_job(args)


def _run_autotest_job(args):
    """Run a job as seen from Autotest.

    This include some Autotest setup and cleanup around lucifer starting
    proper.
    """
    models = autotest.load('frontend.afe.models')
    job = models.Job.objects.get(id=args.job_id)
    if args.lucifer_level == 'STARTING':
        _prepare_autotest_job_files(args, job)
    handler = _make_handler(args, job)
    ret = _run_lucifer_job(handler, args, job)
    if handler.completed:
        _mark_handoff_completed(args.job_id)
    return ret


def _prepare_autotest_job_files(args, job):
    jobx.prepare_control_file(job, args.results_dir)
    jobx.prepare_keyvals_files(job, args.results_dir)


def _make_handler(args, job):
    """Make event handler for lucifer_run_job."""
    assert not (args.lucifer_level == 'GATHERING'
                and args.autoserv_exit is None)
    return handlers.EventHandler(
            metrics=handlers.Metrics(),
            job=job,
            autoserv_exit=args.autoserv_exit,
    )


def _run_lucifer_job(event_handler, args, job):
    """Run lucifer_run_job.

    Issued events will be handled by event_handler.

    @param event_handler: callable that takes an Event
    @param args: parsed arguments
    @returns: exit status of lucifer_run_job
    """
    command_args = [args.run_job_path]
    command_args.extend([
            '-autotestdir', autotest.AUTOTEST_DIR,
            '-watcherpath', args.watcher_path,

            '-abortsock', _abort_sock_path(args.jobdir, args.job_id),
            '-hosts', ','.join(jobx.hostnames(job)),

            '-x-level', args.lucifer_level,
            '-x-resultsdir', args.results_dir,
    ])
    _add_level_specific_args(command_args, args, job)
    return eventlib.run_event_command(
            event_handler=event_handler, args=command_args)


def _add_level_specific_args(command_args, args, job):
    """Add level specific arguments for lucifer_run_job.

    command_args is modified in place.
    """
    if args.lucifer_level == 'STARTING':
        _add_starting_args(command_args, args, job)
    elif args.lucifer_level == 'GATHERING':
        _add_gathering_args(command_args, args, job)
    else:
        raise Exception('Invalid lucifer level %s' % args.lucifer_level)


def _add_starting_args(command_args, args, job):
    """Add STARTING level arguments for lucifer_run_job.

    command_args is modified in place.
    """
    RebootAfter = autotest.load('frontend.afe.model_attributes').RebootAfter
    command_args.extend([
        '-x-control-file', jobx.control_file_path(args.results_dir),
    ])
    command_args.extend(['-x-execution-tag', args.execution_tag])
    command_args.extend(['-x-job-owner', job.owner])
    command_args.extend(['-x-job-name', job.name])
    command_args.extend(
            ['-x-reboot-after',
             RebootAfter.get_string(job.reboot_after).lower()])
    if job.run_reset:
        command_args.append('-x-run-reset')
    command_args.extend(['-x-test-retries', str(job.test_retry)])
    if jobx.is_client_job(job):
        command_args.append('-x-client-test')
    if jobx.needs_ssp(job):
        command_args.append('-x-require-ssp')
        test_source_build = job.keyval_dict().get('test_source_build', None)
        if test_source_build:
            command_args.extend(['-x-test-source-build', test_source_build])
    if job.parent_job_id:
        command_args.extend(['-x-parent-job-id', str(job.parent_job_id)])


def _add_gathering_args(command_args, args, job):
    """Add GATHERING level arguments for lucifer_run_job.

    command_args is modified in place.
    """
    del job
    command_args.extend([
        '-x-autoserv-exit', str(args.autoserv_exit),
    ])
    if args.need_gather:
        command_args.extend([
                '-x-need-gather',
                '-x-num-tests-failed', str(args.num_tests_failed),
        ])


def _mark_handoff_completed(job_id):
    models = autotest.load('frontend.afe.models')
    handoff = models.JobHandoff.objects.get(job_id=job_id)
    handoff.completed = True
    handoff.save()


def _abort_sock_path(jobdir, job_id):
    return _lease_path(jobdir, job_id) + '.sock'


def _lease_path(jobdir, job_id):
    return os.path.join(jobdir, str(job_id))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
