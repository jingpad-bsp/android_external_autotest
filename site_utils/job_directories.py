import abc
import datetime
import glob
import logging
import os
import time

import common
from autotest_lib.server import frontend

_AFE = frontend.AFE(debug=False)

JOB_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

def _is_job_expired(age_limit, timestamp):
  """Check whether a job timestamp is older than an age limit.

  @param age_limit: Minimum age, measured in days.  If the value is
                    not positive, the job is always expired.
  @param timestamp: Timestamp of the job whose age we are checking.
                    The format must match JOB_TIME_FORMAT.

  @returns True iff the job is old enough to be expired.
  """
  if age_limit <= 0:
    return True
  job_time = datetime.datetime.strptime(timestamp, JOB_TIME_FORMAT)
  expiration = job_time + datetime.timedelta(days=age_limit)
  return datetime.datetime.now() >= expiration


class _JobDirectory(object):
  """State associated with a job to be offloaded.

  The full life-cycle of a job (including failure events that
  normally don't occur) looks like this:
   1. The job's results directory is discovered by
      `get_job_directories()`, and a job instance is created for it.
   2. Calls to `offload()` have no effect so long as the job
      isn't complete in the database and the job isn't expired
      according to the `age_limit` parameter.
   3. Eventually, the job is both finished and expired.  The next
      call to `offload()` makes the first attempt to offload the
      directory to GS.  Offload is attempted, but fails to complete
      (e.g. because of a GS problem).
   4. After the first failed offload `is_offloaded()` is false,
      but `is_reportable()` is also false, so the failure is not
      reported.
   5. Another call to `offload()` again tries to offload the
      directory, and again fails.
   6. After a second failure, `is_offloaded()` is false and
      `is_reportable()` is true, so the failure generates an e-mail
      notification.
   7. Finally, a call to `offload()` succeeds, and the directory no
      longer exists.  Now `is_offloaded()` is true, so the job
      instance is deleted, and future failures will not mention this
      directory any more.

  Only steps 1. and 7. are guaranteed to occur.  The others depend
  on the timing of calls to `offload()`, and on the reliability of
  the actual offload process.

  """

  __metaclass__ = abc.ABCMeta

  GLOB_PATTERN = None   # must be redefined in subclass

  def __init__(self, resultsdir):
    self._dirname = resultsdir
    self._id = os.path.basename(resultsdir).split('-')[0]
    self._offload_count = 0
    self._first_offload_start = 0

  @classmethod
  def get_job_directories(cls):
    """Return a list of directories of jobs that need offloading."""
    return [d for d in glob.glob(cls.GLOB_PATTERN) if os.path.isdir(d)]

  @abc.abstractmethod
  def get_timestamp_if_finished(self):
    """Return this job's timestamp from the database.

    If the database has not marked the job as finished, return
    `None`.  Otherwise, return a timestamp for the job.  The
    timestamp is to be used to determine expiration in
    `_is_job_expired()`.

    @return Return `None` if the job is still running; otherwise
            return a string with a timestamp in the appropriate
            format.
    """
    raise NotImplementedError("_JobDirectory.get_timestamp_if_finished")

  def enqueue_offload(self, queue, age_limit):
    """Enqueue the job for offload, if it's eligible.

    The job is eligible for offloading if the database has marked
    it finished, and the job is older than the `age_limit`
    parameter.

    If the job is eligible, offload processing is requested by
    passing the `queue` parameter's `put()` method a sequence with
    the job's `_dirname` attribute and its directory name.

    @param queue     If the job should be offloaded, put the offload
                     parameters into this queue for processing.
    @param age_limit Minimum age for a job to be offloaded.  A value
                     of 0 means that the job will be offloaded as
                     soon as it is finished.

    """
    if not self._offload_count:
      timestamp = self.get_timestamp_if_finished()
      if not timestamp:
        logging.debug('Skipping %s - not finished.', self._dirname)
        return
      if not _is_job_expired(age_limit, timestamp):
        logging.debug('Skipping %s - not old enough.', self._dirname)
        return
      self._first_offload_start = time.time()
    logging.debug('Processing %s', self._dirname)
    self._offload_count += 1
    queue.put([self._dirname, os.path.dirname(self._dirname)])

  def is_offloaded(self):
    """Return whether this job has been successfully offloaded."""
    return not os.path.exists(self._dirname)

  def is_reportable(self):
    """Return whether this job has a reportable failure."""
    return self._offload_count > 1

  def get_failure_time(self):
    """Return the time of the first offload failure."""
    return self._first_offload_start

  def get_failure_count(self):
    """Return the number of times this job has failed to offload."""
    return self._offload_count

  def get_job_directory(self):
    """Return the name of this job's results directory."""
    return self._dirname


class RegularJobDirectory(_JobDirectory):
  """Subclass of _JobDirectory for regular test jobs."""

  GLOB_PATTERN = '[0-9]*-*'

  def get_timestamp_if_finished(self):
    entry = _AFE.run('get_jobs', id=self._id, finished=True)
    return entry[0]['created_on'] if entry else None


class SpecialJobDirectory(_JobDirectory):
  """Subclass of _JobDirectory for special (per-host) jobs."""

  GLOB_PATTERN = 'hosts/*/[0-9]*-*'

  def __init__(self, resultsdir):
    super(SpecialJobDirectory, self).__init__(resultsdir)

  def get_timestamp_if_finished(self):
    entry = _AFE.run('get_special_tasks', id=self._id, is_complete=True)
    return entry[0]['time_started'] if entry else None
