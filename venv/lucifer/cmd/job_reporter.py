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
import datetime
import logging
import os
import sys

from lucifer import autotest
from lucifer import eventlib
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
        autotest.patch()
        return _main(args)


def _parse_args_and_configure_logging(args):
    parser = argparse.ArgumentParser(prog='job_reporter', description=__doc__)
    loglib.add_logging_options(parser)
    parser.add_argument('--run-job-path', default='/usr/bin/lucifer_run_job',
                        help='Path to lucifer_run_job binary')
    parser.add_argument('--jobdir', default='/usr/local/autotest/leases',
                        help='Path to job leases directory.')
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


def _main(args):
    """Main program body, running under a lease file.

    @param args: Namespace object containing parsed arguments
    """
    ts_mon_config = autotest.chromite_load('ts_mon_config')
    metrics = autotest.chromite_load('metrics')
    with ts_mon_config.SetupTsMonGlobalState(
            'autotest_scheduler', short_lived=True):
        atexit.register(metrics.flush)
        handler = _make_handler(args)
        return _run_job(args.run_job_path, handler, args)


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
    return _EventHandler(
            models=models,
            metrics=_Metrics(),
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


def _abort_sock_path(jobdir, job_id):
    return _lease_path(jobdir, job_id) + '.sock'


def _lease_path(jobdir, job_id):
    return os.path.join(jobdir, str(job_id))


class _EventHandler(object):
    """Event handling dispatcher.

    Event handlers are implemented as methods named _handle_<event value>.

    Each handler method must handle its exceptions accordingly.  If an
    exception escapes, the job dies on the spot.
    """

    def __init__(self, models, metrics, job, autoserv_exit):
        """Initialize instance.

        @param models: reference to frontend.afe.models
        @param metrics: _Metrics instance
        @param job: Job instance to own
        @param hqes: list of HostQueueEntry instances for the job
        @param autoserv_exit: autoserv exit status
        """
        self._models = models
        self._metrics = metrics
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
            self._set_completed_status(hqe, final_status)
        if final_status is not self._models.HostQueueEntry.Status.ABORTED:
            _stop_prejob_hqes(self._models, self._job)
        if self._job.shard_id is not None:
            # If shard_id is None, the job will be synced back to the master
            self._job.shard_id = None
            self._job.save()

    def _final_status(self):
        Status = self._models.HostQueueEntry.Status
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

    def _set_completed_status(self, hqe, status):
        """Set completed status of HQE.

        This is a cleaned up version of the one in scheduler_models to work
        with Django models.
        """
        hqe.status = status
        hqe.active = False
        hqe.complete = True
        if hqe.started_on:
            hqe.finished_on = datetime.datetime.now()
        hqe.save()
        self._metrics.send_hqe_completion(hqe)
        self._metrics.send_hqe_duration(hqe)


class _Metrics(object):

    """Class for sending job metrics."""

    def __init__(self):
        # Metrics
        metrics = autotest.chromite_load('metrics')
        self._hqe_completion_metric = metrics.Counter(
                'chromeos/autotest/scheduler/hqe_completion_count')

        # Autotest libs
        self._scheduler_models = autotest.load('scheduler.scheduler_models')
        self._labellib = autotest.load('utils.labellib')

        # Chromite libs
        self._cloud_trace = autotest.chromite_load('cloud_trace')

        # Other libs
        self._types = autotest.deps_load(
                'google.protobuf.internal.well_known_types')


    def send_hqe_completion(self, hqe):
        """Send ts_mon metrics for HQE completion."""
        fields = {
                'status': hqe.status.lower(),
                'board': 'NO_HOST',
                'pool': 'NO_HOST',
        }
        if hqe.host:
            labels = self._labellib.LabelsMapping.from_host(hqe.host)
            fields['board'] = labels.get('board', '')
            fields['pool'] = labels.get('pool', '')
        self._hqe_completion_metric.increment(fields=fields)

    def send_hqe_duration(self, hqe):
        """Send CloudTrace metrics for HQE duration."""
        if not (hqe.started_on and hqe.finished_on):
            return
        cloud_trace = self._cloud_trace
        hqe_trace_id = self._scheduler_models.hqe_trace_id
        types = self._types

        span = cloud_trace.Span(
                'HQE', spanId='0', traceId=hqe_trace_id(hqe.id))
        span.startTime = types.Timestamp()
        span.startTime.FromDatetime(hqe.started_on)
        span.endTime = types.Timestamp()
        span.endTime.FromDatetime(hqe.finished_on)
        cloud_trace.LogSpan(span)


def _stop_prejob_hqes(models, job):
    """Stop pending HQEs for a job (for synch_count)."""
    not_yet_run = _get_prejob_hqes(models, job)
    if not_yet_run.count() == job.synch_count:
        return
    entries_to_stop = _get_prejob_hqes(models, job, include_active=False)
    for hqe in entries_to_stop:
        if hqe.status == models.HostQueueEntry.Status.PENDING:
            hqe.host.status = models.Host.Status.READY
            hqe.host.save()
        hqe.status = models.HostQueueEntry.Status.STOPPED
        hqe.save()


def _get_prejob_hqes(models, job, include_active=True):
    """Return a queryset of not run HQEs for the job (for synch_count)."""
    if include_active:
        statuses = list(models.HostQueueEntry.PRE_JOB_STATUSES)
    else:
        statuses = list(models.HostQueueEntry.IDLE_PRE_JOB_STATUSES)
    return models.HostQueueEntry.objects.filter(
            job=job, status__in=statuses)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
