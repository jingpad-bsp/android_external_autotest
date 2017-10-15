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
    autotest.load('frontend.setup_django_environment')
    _main_loop(jobdir=args.jobdir)
    return 0


def _main_loop(jobdir):
    while True:
        _main_loop_body(jobdir)
        time.sleep(60)


def _main_loop_body(jobdir):
    _process_expired_jobs(jobdir)
    _abort_timed_out_jobs(jobdir)
    _abort_jobs_marked_aborting(jobdir)
    _abort_special_tasks_marked_aborted()
    # TODO(crbug.com/748234): abort_jobs_past_max_runtime goes into
    # job_shepherd


def _process_expired_jobs(jobdir):
    leases = leasing.get_expired_leases(jobdir)
    job_ids = {job.id for job in leasing.get_expired_jobs(jobdir)}
    _mark_aborted(job_ids)
    # Clean up files after marking them aborted in case we crash.
    for lease in leases:
        lease.clean()


def _abort_timed_out_jobs(jobdir):
    models = autotest.load('frontend.afe.models')
    for lease in leasing.get_timed_out_leases(models.Job, jobdir):
        lease.abort()


def _abort_jobs_marked_aborting(jobdir):
    models = autotest.load('frontend.afe.models')
    for lease in leasing.get_marked_aborting_leases(models.Job, jobdir):
        lease.abort()


def _abort_special_tasks_marked_aborted():
    # TODO(crbug.com/748234): Special tasks not implemented yet.  This
    # would abort jobs running on the behalf of special tasks and thus
    # need to check a different database table.
    pass


def _mark_aborted(job_ids):
    """Mark jobs aborted in database."""
    models = autotest.load('frontend.afe.models')
    jobs = (models.Job.objects
            .filter(id__in=job_ids)
            .prefetch_related('hostqueueentry'))
    for job in jobs:
        job.abort()


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
