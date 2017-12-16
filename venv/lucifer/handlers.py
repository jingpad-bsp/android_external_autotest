# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Event handlers."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging
import datetime

from lucifer import autotest

logger = logging.getLogger(__name__)


class EventHandler(object):
    """Event handling dispatcher.

    Event handlers are implemented as methods named _handle_<event value>.

    Each handler method must handle its exceptions accordingly.  If an
    exception escapes, the job dies on the spot.
    """

    def __init__(self, models, metrics, job, autoserv_exit):
        """Initialize instance.

        @param models: reference to frontend.afe.models
        @param metrics: Metrics instance
        @param job: frontend.afe.models.Job instance to own
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
        for hqe in self._job.hostqueueentry_set.all():
            self._set_completed_status(hqe, final_status)
        if final_status is not self._models.HostQueueEntry.Status.ABORTED:
            _stop_prejob_hqes(self._models, self._job)
        if self._job.shard_id is not None:
            # If shard_id is None, the job will be synced back to the master
            self._job.shard_id = None
            self._job.save()

    def _final_status(self):
        Status = self._models.HostQueueEntry.Status
        if _job_aborted(self._job):
            return Status.ABORTED
        if self._autoserv_exit == 0:
            return Status.COMPLETED
        return Status.FAILED

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


class Metrics(object):

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


def _job_aborted(job):
    for hqe in job.hostqueueentry_set.all():
        if hqe.aborted:
            return True
    return False


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
