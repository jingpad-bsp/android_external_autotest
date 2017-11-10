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

import argparse
import logging
import os
import sys

from lucifer import autotest
from lucifer import eventlib
from lucifer import loglib

logger = logging.getLogger(__name__)


def main(args):
    """Main function

    @param args: list of command line args
    """
    args = _parse_args_and_configure_logging(args)
    autotest.patch()
    handler = _make_handler(args)
    return _run_job(args.run_job_path, handler, args)


def _parse_args_and_configure_logging(args):
    parser = argparse.ArgumentParser(prog='job_reporter', description=__doc__)
    loglib.add_logging_options(parser)
    parser.add_argument('--run-job-path', default='/usr/bin/lucifer_run_job',
                        help='Path to lucifer_run_job binary')
    parser.add_argument('--jobdir', default='/usr/local/autotest/leases',
                        help='''
Path to job leases directory.  This is used to construct the -leasefile
argument to lucifer_run_job.
''')
    parser.add_argument('--job-id', type=int, default=None,
                        help='Autotest Job ID')
    parser.add_argument('--autoserv-exit', type=int, default=None, help='''
autoserv exit status.  If this is passed, then autoserv will not be run
as the caller has presumably already run it.
''')
    args, extra_args = parser.parse_known_args(args)
    args.run_job_args = extra_args
    loglib.configure_logging_with_args(parser, args)
    return args


def _make_handler(args):
    """Make event handler for lucifer_run_job."""
    models = autotest.load('frontend.afe.models')
    if args.job_id is not None:
        if args.autoserv_exit is None:
            # TODO(crbug.com/748234): autoserv not implemented yet.
            raise NotImplementedError('not implemented yet (crbug.com/748234)')
        job = models.Job.objects.get(id=args.job_id)
    else:
        # TODO(crbug.com/748234): Full jobs not implemented yet.
        raise NotImplementedError('not implemented yet')
    return _EventHandler(models, job, autoserv_exit=args.autoserv_exit)


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
            ['-leasefile', os.path.join(args.jobdir, str(args.job_id))])
    command_args.extend(args.run_job_args)
    return eventlib.run_event_command(event_handler=event_handler,
                                      args=command_args)


class _EventHandler(object):
    """Event handling dispatcher.

    Event handlers are implemented as methods named _handle_<event value>.

    Each handler method must handle its exceptions accordingly.  If an
    exception escapes, the job dies on the spot.
    """

    def __init__(self, models, job, autoserv_exit):
        """Initialize instance.

        @param models: reference to frontend.afe.models
        @param job: Job instance to own
        @param hqes: list of HostQueueEntry instances for the job
        @param autoserv_exit: autoserv exit status
        """
        self._models = models
        self._job = job
        # TODO(crbug.com/748234): autoserv not implemented yet.
        self._autoserv_exit = autoserv_exit

    def __call__(self, event):
        logger.debug('Received event %r', event.name)
        method_name = '_handle_%s' % event.value
        try:
            handler = getattr(self, method_name)
        except AttributeError:
            raise NotImplementedError('%s is not implemented for handling %s',
                                      method_name, event.name)
        handler(event)

    def _handle_starting(self, event):
        # TODO(crbug.com/748234): No event update needed yet.
        pass

    def _handle_parsing(self, event):
        # TODO(crbug.com/748234): monitor_db leaves the HQEs in parsing
        # for now
        pass

    def _handle_completed(self, _event):
        final_status = self._final_status()
        for hqe in self._hqes:
            hqe.set_status(final_status)

    def _final_status(self):
        afe_models = autotest.load('frontend.afe.models')
        Status = afe_models.HostQueueEntry.Status
        if self._job_was_aborted():
            return Status.ABORTED
        if self._autoserv_exit == 0:
            return Status.COMPLETED
        return Status.FAILED

    @property
    def _hqes(self):
        return self._models.HostQueueEntry.objects.filter(job_id=self._job.id)

    def _job_was_aborted(self):
        for hqe in self._hqes:
            if hqe.aborted:
                return True
        return False


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
