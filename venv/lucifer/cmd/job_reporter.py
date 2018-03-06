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


def main(args):
    """Main function

    @param args: list of command line args
    """
    args = _parse_args_and_configure_logging(args)
    logger.info('Starting with args: %r', args)
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
                        help='Path to job leases directory.')

    # STARTING flags
    # TODO(ayatane): Will be added later

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
    loglib.configure_logging_with_args(parser, args)
    return args


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
    handler = _make_handler(args)
    ret = _run_lucifer_job(handler, args)
    if handler.completed:
        _mark_handoff_completed(args.job_id)
    return ret


def _make_handler(args):
    """Make event handler for lucifer_run_job."""
    models = autotest.load('frontend.afe.models')
    assert not (args.lucifer_level == 'GATHERING'
                and args.autoserv_exit is None)
    job = models.Job.objects.get(id=args.job_id)
    return handlers.EventHandler(
            metrics=handlers.Metrics(),
            job=job,
            autoserv_exit=args.autoserv_exit,
    )


def _run_lucifer_job(event_handler, args):
    """Run lucifer_run_job.

    Issued events will be handled by event_handler.

    @param event_handler: callable that takes an Event
    @param args: parsed arguments
    @returns: exit status of lucifer_run_job
    """
    models = autotest.load('frontend.afe.models')
    command_args = [args.run_job_path]
    job = models.Job.objects.get(id=args.job_id)
    command_args.extend([
            '-autotestdir', autotest.AUTOTEST_DIR,
            '-watcherpath', args.watcher_path,

            '-abortsock', _abort_sock_path(args.jobdir, args.job_id),
            '-hosts', ','.join(jobx.hostnames(job)),

            '-x-level', args.lucifer_level,
            '-x-resultsdir', args.results_dir,
    ])
    _add_level_specific_args(command_args, args)
    return eventlib.run_event_command(
            event_handler=event_handler, args=command_args)


def _add_level_specific_args(command_args, args):
    """Add level specific arguments for lucifer_run_job.

    command_args is modified in place.
    """
    if args.lucifer_level == 'STARTING':
        _add_starting_args(command_args, args)
    elif args.lucifer_level == 'GATHERING':
        _add_gathering_args(command_args, args)
    else:
        raise Exception('Invalid lucifer level %s' % args.lucifer_level)


def _add_starting_args(command_args, args):
    """Add STARTING level arguments for lucifer_run_job.

    command_args is modified in place.
    """
    del command_args, args
    raise NotImplementedError('Lucifer STARTING not implemented yet')


def _add_gathering_args(command_args, args):
    """Add GATHERING level arguments for lucifer_run_job.

    command_args is modified in place.
    """
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
    sys.exit(main(sys.argv[1:]))
