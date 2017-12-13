# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Monitor jobs and abort them as necessary.

This daemon does a number of upkeep tasks:

* When a process owning a job crashes, job_aborter will mark the job as
  aborted in the database and clean up its lease files.

* When a job is marked aborted in the database, job_aborter will signal
  the process owning the job to abort.

See also http://goto.google.com/monitor_db_per_job_refactor
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import datetime
import logging
import sys
import time

from lucifer import autotest
from lucifer import leasing
from lucifer import loglib

logger = logging.getLogger(__name__)


def main(args):
    """Main function

    @param args: list of command line args
    """

    parser = argparse.ArgumentParser(prog='job_aborter', description=__doc__)
    parser.add_argument('--jobdir', required=True)
    loglib.add_logging_options(parser)
    args = parser.parse_args(args)
    loglib.configure_logging_with_args(parser, args)

    autotest.monkeypatch()
    _main_loop(jobdir=args.jobdir)
    return 0


def _main_loop(jobdir):
    transaction = autotest.deps_load('django.db.transaction')

    @transaction.commit_manually
    def flush_transaction():
        """Flush transaction https://stackoverflow.com/questions/3346124/"""
        transaction.commit()

    while True:
        logger.debug('Tick')
        _main_loop_body(jobdir)
        flush_transaction()
        time.sleep(20)


def _main_loop_body(jobdir):
    models = autotest.load('frontend.afe.models')
    active_leases = {
            lease.id: lease for lease in leasing.leases_iter(jobdir)
            if not lease.expired()
    }
    _mark_expired_jobs_failed(models, active_leases)
    _abort_timed_out_jobs(models, active_leases)
    _abort_jobs_marked_aborting(models, active_leases)
    _abort_special_tasks_marked_aborted()
    _clean_up_expired_leases(jobdir)
    # TODO(crbug.com/748234): abort_jobs_past_max_runtime goes into
    # lucifer_run_job


def _mark_expired_jobs_failed(models, active_leases):
    """Mark expired jobs failed.

    Expired jobs are jobs that have an incomplete JobHandoff and that do
    not have an active lease.  These jobs have been handed off to a
    job_reporter, but that job_reporter has crashed.  These jobs are
    marked failed in the database.

    @param models: frontend.afe.models
    @param active_leases: dict mapping job ids to Leases.
    """
    logger.debug('Looking for expired jobs')
    job_ids_to_mark = []
    for handoff in _incomplete_handoffs_queryset(models.JobHandoff):
        logger.debug('Found handoff: %d', handoff.job_id)
        if handoff.job_id not in active_leases:
            logger.debug('Handoff %d is missing active lease', handoff.job_id)
            job_ids_to_mark.append(handoff.job_id)
    _mark_failed(models, job_ids_to_mark)


def _abort_timed_out_jobs(models, active_leases):
    """Send abort to timed out jobs.

    @param models: frontend.afe.models
    @param active_leases: dict mapping job ids to Leases.
    """
    for job in _timed_out_jobs_queryset(models.Job):
        if job.id in active_leases:
            active_leases[job.id].abort()


def _abort_jobs_marked_aborting(models, active_leases):
    """Send abort to jobs marked aborting in Autotest database.

    @param models: frontend.afe.models
    @param active_leases: dict mapping job ids to Leases.
    """
    for job in _aborting_jobs_queryset(models.Job):
        if job.id in active_leases:
            active_leases[job.id].abort()


def _abort_special_tasks_marked_aborted():
    # TODO(crbug.com/748234): Special tasks not implemented yet.  This
    # would abort jobs running on the behalf of special tasks and thus
    # need to check a different database table.
    pass


def _clean_up_expired_leases(jobdir):
    """Clean up files for expired leases.

    We only care about active leases, so we can remove the stale files
    for expired leases.
    """
    for lease in leasing.leases_iter(jobdir):
        if lease.expired():
            lease.cleanup()


_JOB_GRACE_SECS = 10


def _incomplete_handoffs_queryset(JobHandoff):
    """Return a QuerySet of incomplete JobHandoffs.

    JobHandoff created within a cutoff period are exempt to allow the
    job the chance to acquire its lease file; otherwise, incomplete jobs
    without an active lease are considered dead.

    @param JobHandoff: Django model for JobHandoff
    @returns: Django QuerySet
    """
    # Time ---*---------|---------*-------|--->
    #    incomplete   cutoff   newborn   now
    cutoff = (datetime.datetime.now()
              - datetime.timedelta(seconds=_JOB_GRACE_SECS))
    return JobHandoff.objects.filter(completed=False, created__lt=cutoff)


def _timed_out_jobs_queryset(Job):
    """Return a QuerySet of timed out Jobs.

    @param Job: Django model for Job
    @returns: Django QuerySet
    """
    return (
            Job.objects
            .filter(hostqueueentry__complete=False)
            .extra(where=['created_on + INTERVAL timeout_mins MINUTE < NOW()'])
            .distinct()
    )


def _aborting_jobs_queryset(Job):
    """Return a QuerySet of aborting Jobs.

    @param Job: Django model for Job
    @returns: Django QuerySet
    """
    return (
            Job.objects
            .filter(hostqueueentry__aborted=True)
            .filter(hostqueueentry__complete=False)
            .distinct()
    )


def _filter_leased(jobdir, dbjobs):
    """Filter Job models for leased jobs.

    Yields pairs of Job model and Lease instances.

    @param jobdir: job lease file directory
    @param dbjobs: iterable of Django model Job instances
    @returns: iterator of Leases
    """
    our_jobs = {job.id: job for job in leasing.leases_iter(jobdir)}
    for dbjob in dbjobs:
        if dbjob.id in our_jobs:
            yield dbjob, our_jobs[dbjob.id]


def _mark_failed(models, job_ids):
    """Mark jobs failed in database.

    This also marks the corresponding JobHandoffs as completed.
    """
    if not job_ids:
        return
    logger.info('Marking jobs failed: %r', job_ids)
    (models.HostQueueEntry.objects
     .filter(job_id__in=job_ids)
     .update(complete=True,
             status=models.HostQueueEntry.Status.FAILED))
    (models.HostQueueEntry.objects
     .filter(job_id__in=job_ids)
     .exclude(started_on=None)
     .update(finished_on=datetime.datetime.now()))
    (models.JobHandoff.objects
     .filter(job_id__in=job_ids)
     .update(completed=True))


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
