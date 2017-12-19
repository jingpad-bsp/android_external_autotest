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
from lucifer import leasing
from lucifer import loglib

logger = logging.getLogger(__name__)


def main(args):
    """Main function

    @param args: list of command line args
    """
    args = _parse_args_and_configure_logging(args)
    lease_path = _lease_path(args.jobdir, args.job_id)
    with leasing.obtain_lease(lease_path):
        autotest.monkeypatch()
        return _main(args)


def _parse_args_and_configure_logging(args):
    parser = argparse.ArgumentParser(prog='job_reporter', description=__doc__)
    loglib.add_logging_options(parser)
    parser.add_argument('--run-job-path', default='/usr/bin/lucifer_run_job',
                        help='Path to lucifer_run_job binary')
    parser.add_argument('--jobdir', default='/usr/local/autotest/leases',
                        help='Path to job leases directory.')
    parser.add_argument('--job-id', type=int, default=None, required=True,
                        help='Autotest Job ID')
    parser.add_argument('--autoserv-exit', type=int, default=None, help='''
autoserv exit status.  If this is passed, then autoserv will not be run
as the caller has presumably already run it.
''')
    parser.add_argument('run_job_args', nargs='*',
                        help='Arguments to pass to lucifer_run_job')
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
            'autotest_scheduler', short_lived=True):
        atexit.register(metrics.Flush)
        handler = _make_handler(args)
        ret = _run_job(args.run_job_path, handler, args)
        _mark_handoff_completed(args.job_id)
        return ret


def _make_handler(args):
    """Make event handler for lucifer_run_job."""
    models = autotest.load('frontend.afe.models')
    if args.autoserv_exit is None:
        # TODO(crbug.com/748234): autoserv not implemented yet.
        raise NotImplementedError('not implemented yet (crbug.com/748234)')
    job = models.Job.objects.get(id=args.job_id)
    return handlers.EventHandler(
            models=models,
            metrics=handlers.Metrics(),
            job=job,
            autoserv_exit=args.autoserv_exit,
    )


def _run_job(path, event_handler, args):
    """Run lucifer_run_job.

    Issued events will be handled by event_handler.

    @param path: path to lucifer_run_job binary
    @param event_handler: callable that takes an Event
    @param args: parsed arguments
    @returns: exit status of lucifer_run_job
    """
    command_args = [path]
    command_args.extend(
            ['-abortsock', _abort_sock_path(args.jobdir, args.job_id)])
    command_args.extend(args.run_job_args)
    return eventlib.run_event_command(event_handler=event_handler,
                                      args=command_args)


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
