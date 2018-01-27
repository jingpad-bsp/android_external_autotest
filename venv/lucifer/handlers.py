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

    Instances have one public attribute completed.  completed is set to
    True once the final COMPLETED event is received and the handler
    finishes.
    """

    def __init__(self, metrics, job, autoserv_exit):
        """Initialize instance.

        @param metrics: Metrics instance
        @param job: frontend.afe.models.Job instance to own
        @param hqes: list of HostQueueEntry instances for the job
        @param autoserv_exit: autoserv exit status
        """
        self.completed = False
        self._metrics = metrics
        self._job = job
        # TODO(crbug.com/748234): autoserv not implemented yet.
        self._autoserv_exit = autoserv_exit

    def __call__(self, event, msg):
        logger.debug('Received event %r with message %r', event.name, msg)
        method_name = '_handle_%s' % event.value
        try:
            handler = getattr(self, method_name)
        except AttributeError:
            raise NotImplementedError('%s is not implemented for handling %s',
                                      method_name, event.name)
        handler(event, msg)

    def _handle_starting(self, event, msg):
        # TODO(crbug.com/748234): No event update needed yet.
        pass

    def _handle_gathering(self, event, msg):
        # TODO(crbug.com/794779): monitor_db leaves HQEs in GATHERING
        pass

    def _handle_x_tests_done(self, _event, msg):
        autoserv_exit, failures = msg.split(',')
        success = (autoserv_exit == 0 and failures == 0)
        reset_after_failure = not self._job.run_reset and not success
        if self._should_reboot_duts(autoserv_exit, failures,
                                    reset_after_failure):
            _create_cleanup_for_job_hosts(self._job)
        else:
            _mark_job_hosts_ready(self._job)
        if not reset_after_failure:
            return
        self._metrics.send_reset_after_failure(autoserv_exit, failures)
        _create_reset_for_job_hosts(self._job)

    def _handle_parsing(self, _event, _msg):
        models = autotest.load('frontend.afe.models')
        PARSING = models.HostQueueEntry.Status.PARSING
        hqes = self._job.hostqueueentry_set.all()
        hqes.update(status=PARSING)

    def _handle_completed(self, _event, _msg):
        models = autotest.load('frontend.afe.models')
        final_status = self._final_status()
        for hqe in self._job.hostqueueentry_set.all():
            self._set_completed_status(hqe, final_status)
        if final_status is not models.HostQueueEntry.Status.ABORTED:
            _stop_prejob_hqes(self._job)
        if self._job.shard_id is not None:
            # If shard_id is None, the job will be synced back to the master
            self._job.shard_id = None
            self._job.save()
        self.completed = True

    def _should_reboot_duts(self, autoserv_exit, failures, reset_after_failure):
        models = autotest.load('frontend.afe.models')
        reboot_after = self._job.reboot_after
        if self._final_status() == models.HostQueueEntry.Status.ABORTED:
            return True
        elif reboot_after == models.Job.RebootAfter.ALWAYS:
            return True
        elif reboot_after == models.Job.RebootAfter.IF_ALL_TESTS_PASSED:
            return autoserv_exit == 0 and failures == 0
        else:
            return failures > 0 and not reset_after_failure

    def _final_status(self):
        models = autotest.load('frontend.afe.models')
        Status = models.HostQueueEntry.Status
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
        self._reset_after_failure_metric = metrics.Counter(
                'chromeos/autotest/scheduler/postjob_tasks/'
                'reset_after_failure')

    def send_hqe_completion(self, hqe):
        """Send ts_mon metrics for HQE completion."""
        fields = {
                'status': hqe.status.lower(),
                'board': 'NO_HOST',
                'pool': 'NO_HOST',
        }
        if hqe.host:
            labellib = autotest.load('utils.labellib')
            labels = labellib.LabelsMapping.from_host(hqe.host)
            fields['board'] = labels.get('board', '')
            fields['pool'] = labels.get('pool', '')
        self._hqe_completion_metric.increment(fields=fields)

    def send_hqe_duration(self, hqe):
        """Send CloudTrace metrics for HQE duration."""
        if not (hqe.started_on and hqe.finished_on):
            return
        scheduler_models = autotest.load('scheduler.scheduler_models')
        cloud_trace = autotest.chromite_load('cloud_trace')
        types = autotest.deps_load('google.protobuf.internal.well_known_types')
        hqe_trace_id = scheduler_models.hqe_trace_id

        span = cloud_trace.Span(
                'HQE', spanId='0', traceId=hqe_trace_id(hqe.id))
        span.startTime = types.Timestamp()
        span.startTime.FromDatetime(hqe.started_on)
        span.endTime = types.Timestamp()
        span.endTime.FromDatetime(hqe.finished_on)
        cloud_trace.LogSpan(span)

    def send_reset_after_failure(self, autoserv_exit, failures):
        """Send reset_after_failure metric."""
        self._reset_after_failure_metric.increment(
                fields={'autoserv_process_success': autoserv_exit == 0,
                        # Yes, this is a boolean
                        'num_tests_failed': failures > 0})


def _job_aborted(job):
    for hqe in job.hostqueueentry_set.all():
        if hqe.aborted:
            return True
    return False


def _stop_prejob_hqes(job):
    """Stop pending HQEs for a job (for synch_count)."""
    models = autotest.load('frontend.afe.models')
    HQEStatus = models.HostQueueEntry.Status
    HostStatus = models.Host.Status
    not_yet_run = _get_prejob_hqes(job)
    if not_yet_run.count() == job.synch_count:
        return
    entries_to_stop = _get_prejob_hqes(job, include_active=False)
    for hqe in entries_to_stop:
        if hqe.status == HQEStatus.PENDING:
            hqe.host.status = HostStatus.READY
            hqe.host.save()
        hqe.status = HQEStatus.STOPPED
        hqe.save()


def _get_prejob_hqes(job, include_active=True):
    """Return a queryset of not run HQEs for the job (for synch_count)."""
    models = autotest.load('frontend.afe.models')
    if include_active:
        statuses = list(models.HostQueueEntry.PRE_JOB_STATUSES)
    else:
        statuses = list(models.HostQueueEntry.IDLE_PRE_JOB_STATUSES)
    return models.HostQueueEntry.objects.filter(
            job=job, status__in=statuses)


def _create_reset_for_job_hosts(job):
    """Create reset tasks for a job's hosts.

    @param job: frontend.afe.models.Job instance
    """
    models = autotest.load('frontend.afe.models')
    User = models.User
    SpecialTask = models.SpecialTask
    for entry in job.hostqueueentry_set.all():
        SpecialTask.objects.create(
                host_id=entry.host.id,
                task=SpecialTask.Task.RESET,
                requested_by=User.objects.get(login=job.owner))


def _create_cleanup_for_job_hosts(job):
    """Create cleanup tasks for a job's hosts.

    @param job: frontend.afe.models.Job instance
    """
    models = autotest.load('frontend.afe.models')
    User = models.User
    SpecialTask = models.SpecialTask
    for entry in job.hostqueueentry_set.all():
        SpecialTask.objects.create(
                host_id=entry.host.id,
                task=SpecialTask.Task.CLEANUP,
                requested_by=User.objects.get(login=job.owner))


def _mark_job_hosts_ready(job):
    """Mark job's hosts READY.

    @param job: frontend.afe.models.Job instance
    """
    models = autotest.load('frontend.afe.models')
    hosts = set(job.hostqueueentry_set.all().values_list('host_id', flat=True))
    (models.Host.objects.filter(id__in=hosts)
     .update(status=models.Host.Status.READY))
