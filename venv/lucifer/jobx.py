# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Extra functions for frontend.afe.models.Job objects.

Most of these exist in tightly coupled forms in legacy Autotest code
(e.g., part of methods with completely unrelated names on Task objects
under multiple layers of abstract classes).  These are defined here to
sanely reuse without having to commit to a long refactor of legacy code
that is getting deleted soon.

It's not really a good idea to define these on the Job class either;
they are specialized and the Job class already suffers from method
bloat.
"""

from lucifer import autotest


def is_hostless(job):
    """Return True if the job is hostless.

    @param job: frontend.afe.models.Job instance
    """
    return bool(hostnames(job))


def hostnames(job):
    """Return a list of hostnames for a job.

    @param job: frontend.afe.models.Job instance
    """
    hqes = job.hostqueueentry_set.all().prefetch_related('host')
    return [hqe.host.hostname for hqe in hqes if hqe.host is not None]


def is_aborted(job):
    """Return if the job is aborted.

    (This means the job is marked for abortion; the job can still be
    running.)

    @param job: frontend.afe.models.Job instance
    """
    for hqe in job.hostqueueentry_set.all():
        if hqe.aborted:
            return True
    return False


def create_reset_for_job_hosts(job):
    """Create reset tasks for a job's hosts.

    See postjob_task.py:GatherLogsTask.epilog

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


def create_cleanup_for_job_hosts(job):
    """Create cleanup tasks for a job's hosts.

    See postjob_task.py:GatherLogsTask.epilog

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


def mark_hosts_ready(job):
    """Mark a job's hosts READY.

    @param job: frontend.afe.models.Job instance
    """
    models = autotest.load('frontend.afe.models')
    _hosts(job).update(status=models.Host.Status.READY)


def _hosts(job):
    """Return a QuerySet for the job's hosts.

    @param job: frontend.afe.models.Job instance
    """
    models = autotest.load('frontend.afe.models')
    host_ids = set(job.hostqueueentry_set.all()
                   .values_list('host_id', flat=True))
    return models.Host.objects.filter(id__in=host_ids)
