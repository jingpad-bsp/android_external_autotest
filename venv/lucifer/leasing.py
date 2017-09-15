# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Job leasing.

Jobs are leased to processes to own and run.  A process owning a job
grabs a fcntl lock on the corresponding job lease file.  If the lock on
the job is released, the owning process is considered dead and the job
lease is considered expired.  Some other process (job_aborter) will need
to make the necessary updates to reflect the job's failure.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import fcntl
import logging
import os

from scandir import scandir

_HEARTBEAT_DEADLINE_SECS = 10 * 60
_HEARTBEAT_SECS = 3 * 60

logger = logging.getLogger(__name__)


def get_expired_leases(jobdir):
    """Yield expired JobLeases in jobdir.

    Expired jobs are jobs whose lease files are no longer locked.

    @param jobdir: job lease file directory
    """
    for lease in _job_leases_iter(jobdir):
        if lease.expired():
            yield lease


def get_timed_out_leases(dbjob_model, jobdir):
    """Yield timed out Jobs that are leased.

    @param dbjob_model: Django model for Job
    @param jobdir: job lease file directory
    """
    all_timed_out_dbjobs = (
            dbjob_model.objects
            .filter(hostqueueentry__complete=False)
            .extra(where=['created_on + INTERVAL timeout_mins MINUTE < NOW()'])
            .distinct()
    )
    for _, lease in _filter_leased(jobdir, all_timed_out_dbjobs):
        yield lease


def get_marked_aborting_leases(dbjob_model, jobdir):
    """Yield Jobs marked for aborting that are leased.

    @param dbjob_model: Django model for Job
    @param jobdir: job lease file directory
    """
    all_aborting_dbjobs = (
            dbjob_model.objects
            .filter(hostqueueentry__aborted=True)
            .filter(hostqueueentry__complete=False)
            .distinct()
    )
    for _, lease in _filter_leased(jobdir, all_aborting_dbjobs):
        yield lease


def make_lease_file(jobdir, job_id):
    """Make lease file corresponding to a job.

    Kept to document/pin public API.  The actual creation happens in the
    job_shepherd (which is written in Go).

    @param jobdir: job lease file directory
    @param job_id: Job ID
    """
    path = os.path.join(jobdir, str(job_id))
    with open(path, 'w'):
        pass
    return path


class JobLease(object):
    "Represents a job lease."

    def __init__(self, entry):
        """Initialize instance.

        @param entry: scandir.DirEntry instance
        """
        self._entry = entry

    @property
    def id(self):
        """Return id of leased job."""
        return int(self._entry.name)

    def expired(self):
        """Return True if the lease is expired."""
        return not _fcntl_locked(self._entry.path)

    def cleanup(self):
        """Remove the lease file."""
        os.unlink(self._entry.path)


def _filter_leased(jobdir, dbjobs):
    """Filter Job models for leased jobs.

    Yields pairs of Job model and JobLease instances.

    @param jobdir: job lease file directory
    @param dbjobs: iterable of Django model Job instances
    """
    our_jobs = {job.id: job for job in _job_leases_iter(jobdir)}
    for dbjob in dbjobs:
        if dbjob.id in our_jobs:
            yield dbjob, our_jobs[dbjob.id]


def _job_leases_iter(jobdir):
    """Yield JobLease instances from jobdir.

    @param jobdir: job lease file directory
    """
    for entry in scandir(jobdir):
        yield JobLease(entry)


def _fcntl_locked(path):
    """Return True if a file is fcntl locked.

    @param path: path to file
    """
    fd = os.open(path, os.O_WRONLY)
    try:
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        return True
    else:
        return False
    finally:
        os.close(fd)
