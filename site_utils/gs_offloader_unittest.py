# Copyright 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import Queue
import datetime
import logging
import os
import shutil
import sys
import tempfile
import time
import unittest

import mox

import common
import gs_offloader
import job_directories

from autotest_lib.scheduler import email_manager

# Test value to use for `days_old`, if nothing else is required.
_TEST_EXPIRATION_AGE = 7

# When constructing sample time values for testing expiration,
# allow this many seconds between the expiration time and the
# current time.
_MARGIN_SECS = 10.0


def _get_options(argv):
    """Helper function to exercise command line parsing.

    @param argv Value of sys.argv to be parsed.

    """
    sys.argv = ['bogus.py'] + argv
    return gs_offloader.parse_options()


class OffloaderOptionsTests(unittest.TestCase):
    """Tests for the `Offloader` constructor.

    Tests that offloader instance fields are set as expected
    for given command line options.

    """

    _REGULAR_ONLY = set([job_directories.RegularJobDirectory])
    _SPECIAL_ONLY = set([job_directories.SpecialJobDirectory])
    _BOTH = _REGULAR_ONLY | _SPECIAL_ONLY

    def test_process_no_options(self):
        """Test default offloader options."""
        offloader = gs_offloader.Offloader(_get_options([]))
        self.assertEqual(set(offloader._jobdir_classes),
                         self._REGULAR_ONLY)
        self.assertEqual(offloader._processes, 1)
        self.assertEqual(offloader._offload_func,
                         gs_offloader.offload_dir)
        self.assertEqual(offloader._age_limit, 0)

    def test_process_all_option(self):
        """Test offloader handling for the --all option."""
        offloader = gs_offloader.Offloader(_get_options(['--all']))
        self.assertEqual(set(offloader._jobdir_classes), self._BOTH)
        self.assertEqual(offloader._processes, 1)
        self.assertEqual(offloader._offload_func,
                         gs_offloader.offload_dir)
        self.assertEqual(offloader._age_limit, 0)

    def test_process_hosts_option(self):
        """Test offloader handling for the --hosts option."""
        offloader = gs_offloader.Offloader(
                _get_options(['--hosts']))
        self.assertEqual(set(offloader._jobdir_classes),
                         self._SPECIAL_ONLY)
        self.assertEqual(offloader._processes, 1)
        self.assertEqual(offloader._offload_func,
                         gs_offloader.offload_dir)
        self.assertEqual(offloader._age_limit, 0)

    def test_parallelism_option(self):
        """Test offloader handling for the --parallelism option."""
        offloader = gs_offloader.Offloader(
                _get_options(['--parallelism', '2']))
        self.assertEqual(set(offloader._jobdir_classes),
                         self._REGULAR_ONLY)
        self.assertEqual(offloader._processes, 2)
        self.assertEqual(offloader._offload_func,
                         gs_offloader.offload_dir)
        self.assertEqual(offloader._age_limit, 0)

    def test_delete_only_option(self):
        """Test offloader handling for the --delete_only option."""
        offloader = gs_offloader.Offloader(
                _get_options(['--delete_only']))
        self.assertEqual(set(offloader._jobdir_classes),
                         self._REGULAR_ONLY)
        self.assertEqual(offloader._processes, 1)
        self.assertEqual(offloader._offload_func,
                         gs_offloader.delete_files)
        self.assertEqual(offloader._age_limit, 0)

    def test_delete_only_option(self):
        """Test offloader handling for the --days_old option."""
        offloader = gs_offloader.Offloader(
                _get_options(['--days_old', '7']))
        self.assertEqual(set(offloader._jobdir_classes),
                         self._REGULAR_ONLY)
        self.assertEqual(offloader._processes, 1)
        self.assertEqual(offloader._offload_func,
                         gs_offloader.offload_dir)
        self.assertEqual(offloader._age_limit, 7)


def _make_timestamp(age_limit, is_expired):
    """Create a timestamp for use by `job_directories._is_job_expired()`.

    The timestamp will meet the syntactic requirements for
    timestamps used as input to `_is_job_expired()`.  If
    `is_expired` is true, the timestamp will be older than
    `age_limit` days before the current time; otherwise, the
    date will be younger.

    @param age_limit    The number of days before expiration of the
                        target timestamp.
    @param is_expired   Whether the timestamp should be expired
                        relative to `age_limit`.

    """
    seconds = -_MARGIN_SECS
    if is_expired:
        seconds = -seconds
    delta = datetime.timedelta(days=age_limit, seconds=seconds)
    reference_time = datetime.datetime.now() - delta
    return reference_time.strftime(job_directories.JOB_TIME_FORMAT)


class JobExpirationTests(unittest.TestCase):
    """Tests to exercise `job_directories._is_job_expired()`."""

    def test_expired(self):
        """Test detection of an expired job."""
        timestamp = _make_timestamp(_TEST_EXPIRATION_AGE, True)
        self.assertTrue(
            job_directories._is_job_expired(
                _TEST_EXPIRATION_AGE, timestamp))


    def test_alive(self):
        """Test detection of a job that's not expired."""
        # N.B.  This test may fail if its run time exceeds more than
        # about _MARGIN_SECS seconds.
        timestamp = _make_timestamp(_TEST_EXPIRATION_AGE, False)
        self.assertFalse(
            job_directories._is_job_expired(
                _TEST_EXPIRATION_AGE, timestamp))


class _MockJobDirectory(job_directories._JobDirectory):
    """Subclass of `_JobDirectory` used as a helper for tests."""

    GLOB_PATTERN = '[0-9]*-*'

    def __init__(self, resultsdir):
        """Create new job in initial state."""
        super(_MockJobDirectory, self).__init__(resultsdir)
        self._destname = 'fubar'
        self._timestamp = None

    def get_timestamp_if_finished(self):
        return self._timestamp

    def set_finished(self, days_old):
        """Make this job appear to be finished.

        After calling this function, calls to `enqueue_offload()`
        will find this job as finished, but not expired and ready
        for offload.  Note that when `days_old` is 0,
        `enqueue_offload()` will treat a finished job as eligible
        for offload.

        @param days_old The value of the `days_old` parameter that
                        will be passed to `enqueue_offload()` for
                        testing.

        """
        self._timestamp = _make_timestamp(days_old, False)

    def set_expired(self, days_old):
        """Make this job eligible to be offloaded.

        After calling this function, calls to `offload` will attempt
        to offload this job.

        @param days_old The value of the `days_old` parameter that
                        will be passed to `enqueue_offload()` for
                        testing.

        """
        self._timestamp = _make_timestamp(days_old, True)

    def set_incomplete(self):
        """Make this job appear to have failed offload just once."""
        self._offload_count += 1
        if not os.path.isdir(self._dirname):
            os.mkdir(self._dirname)

    def set_reportable(self):
        """Make this job be reportable."""
        self._offload_count += 1
        self.set_incomplete()

    def set_complete(self):
        """Make this job be completed."""
        self._offload_count += 1
        if os.path.isdir(self._dirname):
            os.rmdir(self._dirname)


# Below is partial sample of e-mail notification text.  This text is
# deliberately hard-coded and then parsed to create the test data;
# the idea is to make sure the actual text format will be reviewed
# by a human being.
#
# first offload      count  directory
# --+----1----+----  ----+  ----+----1----+----2----+----3
_SAMPLE_DIRECTORIES_REPORT = '''\
=================== ======  ==============================
2014-03-14 15:09:26      1  118-fubar
2014-03-14 15:19:23      2  117-fubar
2014-03-14 15:29:20      6  116-fubar
2014-03-14 15:39:17     24  115-fubar
2014-03-14 15:49:14    120  114-fubar
2014-03-14 15:59:11    720  113-fubar
2014-03-14 16:09:08   5040  112-fubar
2014-03-14 16:19:05  40320  111-fubar
'''


class EmailTemplateTests(mox.MoxTestBase):
    """Test the formatting of e-mail notifications."""

    def setUp(self):
        super(EmailTemplateTests, self).setUp()
        self.mox.StubOutWithMock(email_manager.manager,
                                 'send_email')
        self._joblist = []
        for line in _SAMPLE_DIRECTORIES_REPORT.split('\n')[1 : -1]:
            date_, time_, count, dir_ = line.split()
            job = _MockJobDirectory(dir_)
            job._offload_count = int(count)
            timestruct = time.strptime(
                    "%s %s" % (date_, time_),
                    gs_offloader.ERROR_EMAIL_TIME_FORMAT)
            job._first_offload_start = time.mktime(timestruct)
            # enter the jobs in reverse order, to make sure we
            # test that the output will be sorted.
            self._joblist.insert(0, job)

    def test_email_template(self):
        """Trigger an e-mail report and check its contents."""
        # The last line of the report is a separator that we
        # repeat in the first line of our expected result data.
        # So, we remove that separator from the end of the of
        # the e-mail report message.
        #
        # The last element in the list returned by split('\n')
        # will be an empty string, so to remove the separator,
        # we remove the next-to-last entry in the list.
        report_lines = gs_offloader.ERROR_EMAIL_REPORT_FORMAT.split('\n')
        expected_message = ('\n'.join(report_lines[: -2] +
                                      report_lines[-1 :]) +
                            _SAMPLE_DIRECTORIES_REPORT)
        email_manager.manager.send_email(
            mox.IgnoreArg(), mox.IgnoreArg(), expected_message)
        self.mox.ReplayAll()
        gs_offloader.report_offload_failures(self._joblist)


class GetTimestampTests(mox.MoxTestBase):
    """Test `get_timestamp_if_finished()` for all cases.

    This provides coverage for the implementation in both
    RegularJobDirectory and SpecialJobDirectory.

    """

    def setUp(self):
        super(GetTimestampTests, self).setUp()
        self.mox.StubOutWithMock(job_directories._AFE, 'run')

    def test_finished_regular_job(self):
        """Test getting the timestamp for a finished regular job.

        Tests the return value for
        `RegularJobDirectory.get_timestamp_if_finished()` when
        the AFE indicates the job is finished.

        """
        job = job_directories.RegularJobDirectory('118-fubar')
        timestamp = _make_timestamp(0, True)
        job_directories._AFE.run(
            'get_jobs', id='118', finished=True).AndReturn(
                [{'created_on': timestamp}])
        self.mox.ReplayAll()
        self.assertEqual(timestamp,
                         job.get_timestamp_if_finished())

    def test_unfinished_regular_job(self):
        """Test getting the timestamp for an unfinished regular job.

        Tests the return value for
        `RegularJobDirectory.get_timestamp_if_finished()` when
        the AFE indicates the job is not finished.

        """
        job = job_directories.RegularJobDirectory('118-fubar')
        job_directories._AFE.run(
            'get_jobs', id='118', finished=True).AndReturn(None)
        self.mox.ReplayAll()
        self.assertIsNone(job.get_timestamp_if_finished())

    def test_finished_special_job(self):
        """Test getting the timestamp for a finished special job.

        Tests the return value for
        `SpecialJobDirectory.get_timestamp_if_finished()` when
        the AFE indicates the job is finished.

        """
        job = job_directories.SpecialJobDirectory('hosts/host1/118-reset')
        timestamp = _make_timestamp(0, True)
        job_directories._AFE.run(
            'get_special_tasks', id='118', is_complete=True).AndReturn(
                [{'time_started': timestamp}])
        self.mox.ReplayAll()
        self.assertEqual(timestamp,
                         job.get_timestamp_if_finished())

    def test_unfinished_special_job(self):
        """Test getting the timestamp for an unfinished special job.

        Tests the return value for
        `SpecialJobDirectory.get_timestamp_if_finished()` when
        the AFE indicates the job is not finished.

        """
        job = job_directories.SpecialJobDirectory('hosts/host1/118-reset')
        job_directories._AFE.run(
            'get_special_tasks', id='118', is_complete=True).AndReturn(None)
        self.mox.ReplayAll()
        self.assertIsNone(job.get_timestamp_if_finished())


class _TempResultsDirTestBase(mox.MoxTestBase):
    """Base class for tests using a temporary results directory."""

    REGULAR_JOBLIST = [
        '111-fubar', '112-fubar', '113-fubar', '114-snafu']
    HOST_LIST = ['host1', 'host2', 'host3']
    SPECIAL_JOBLIST = [
        'hosts/host1/333-reset', 'hosts/host1/334-reset',
        'hosts/host2/444-reset', 'hosts/host3/555-reset']

    def setUp(self):
        super(_TempResultsDirTestBase, self).setUp()
        self._resultsroot = tempfile.mkdtemp()
        self._cwd = os.getcwd()
        os.chdir(self._resultsroot)

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self._resultsroot)
        super(_TempResultsDirTestBase, self).tearDown()

    def make_job(self, jobdir):
        """Create a job with results in `self._resultsroot`.

        @param jobdir Name of the subdirectory to be created in
                      `self._resultsroot`.

        """
        os.mkdir(jobdir)
        return _MockJobDirectory(jobdir)

    def make_job_hierarchy(self):
        """Create a sample hierarchy of job directories.

        `self.REGULAR_JOBLIST` is a list of directories for regular
        jobs to be created; `self.SPECIAL_JOBLIST` is a list of
        directories for special jobs to be created.

        """
        for d in self.REGULAR_JOBLIST:
            os.mkdir(d)
        hostsdir = 'hosts'
        os.mkdir(hostsdir)
        for host in self.HOST_LIST:
            os.mkdir(os.path.join(hostsdir, host))
        for d in self.SPECIAL_JOBLIST:
            os.mkdir(d)


class JobDirectoryOffloadTests(_TempResultsDirTestBase):
    """Tests for `_JobDirectory.enqueue_offload()`.

    When testing with a `days_old` parameter of 0, we use
    `set_finished()` instead of `set_expired()`.  This causes the
    job's timestamp to be set in the future.  This is done so as
    to test that when `days_old` is 0, the job is always treated
    as eligible for offload, regardless of the timestamp's value.

    Testing covers the following assertions:
     A. Each time `enqueue_offload()` is called, a message that
        includes the job's directory name will be logged using
        `logging.debug()`, regardless of whether the job was
        enqueued.  Nothing else is allowed to be logged.
     B. If the job is not eligible to be offloaded,
        `_first_offload_start` and `_offload_count` are 0.
     C. If the job is not eligible for offload, nothing is
        enqueued in `queue`.
     D. When the job is offloaded, `_offload_count` increments
        each time.
     E. When the job is offloaded, the appropriate parameters are
        enqueued exactly once.
     F. The first time a job is offloaded, `_first_offload_start` is
        set to the current time.
     G. `_first_offload_start` only changes the first time that the
        job is offloaded.

    The test cases below are designed to exercise all of the
    meaningful state transitions at least once.

    """

    def setUp(self):
        super(JobDirectoryOffloadTests, self).setUp()
        self._job = self.make_job(self.REGULAR_JOBLIST[0])
        self._queue = Queue.Queue()
        self.mox.StubOutWithMock(logging, 'debug')

    def _offload_once(self, days_old):
        """Make one call to the `enqueue_offload()` method.

        This method tests assertion A regarding message
        logging.

        """
        logging.debug(mox.IgnoreArg(), self._job._dirname)
        self.mox.ReplayAll()
        self._job.enqueue_offload(self._queue, days_old)
        self.mox.VerifyAll()
        self.mox.ResetAll()

    def _offload_unexpired_job(self, days_old):
        """Make calls to `enqueue_offload()` for an unexpired job.

        This method tests assertions B and C that calling
        `enqueue_offload()` has no effect.

        """
        self.assertEqual(self._job._offload_count, 0)
        self.assertEqual(self._job._first_offload_start, 0)
        self._offload_once(days_old)
        self._offload_once(days_old)
        self.assertTrue(self._queue.empty())
        self.assertEqual(self._job._offload_count, 0)
        self.assertEqual(self._job._first_offload_start, 0)

    def _offload_expired_once(self, days_old, count):
        """Make one call to `enqueue_offload()` for an expired job.

        This method tests assertions D and E regarding side-effects
        expected when a job is offloaded.

        """
        self._offload_once(days_old)
        self.assertEqual(self._job._offload_count, count)
        self.assertFalse(self._queue.empty())
        v = self._queue.get_nowait()
        self.assertTrue(self._queue.empty())
        self.assertEqual(v, [self._job._dirname, self._job._destname])

    def _offload_expired_job(self, days_old):
        """Make calls to `enqueue_offload()` for a just-expired job.

        This method directly tests assertions F and G regarding
        side-effects on `_first_offload_start`.

        """
        t0 = time.time()
        self._offload_expired_once(days_old, 1)
        t1 = self._job._first_offload_start
        self.assertLessEqual(t1, time.time())
        self.assertGreaterEqual(t1, t0)
        self._offload_expired_once(days_old, 2)
        self.assertEqual(self._job._first_offload_start, t1)
        self._offload_expired_once(days_old, 3)
        self.assertEqual(self._job._first_offload_start, t1)

    def test_case_1_no_expiration(self):
        """Test a series of `enqueue_offload()` calls with `days_old` of 0.

        This tests that offload works as expected if calls are
        made both before and after the job becomes expired.

        """
        self._offload_unexpired_job(0)
        self._job.set_finished(0)
        self._offload_expired_job(0)

    def test_case_2_no_expiration(self):
        """Test a series of `enqueue_offload()` calls with `days_old` of 0.

        This tests that offload works as expected if calls are made
        only after the job becomes expired.

        """
        self._job.set_finished(0)
        self._offload_expired_job(0)

    def test_case_1_with_expiration(self):
        """Test a series of `enqueue_offload()` calls with `days_old` non-zero.

        This tests that offload works as expected if calls are made
        before the job finishes, before the job expires, and after
        the job expires.

        """
        self._offload_unexpired_job(_TEST_EXPIRATION_AGE)
        self._job.set_finished(_TEST_EXPIRATION_AGE)
        self._offload_unexpired_job(_TEST_EXPIRATION_AGE)
        self._job.set_expired(_TEST_EXPIRATION_AGE)
        self._offload_expired_job(_TEST_EXPIRATION_AGE)

    def test_case_2_with_expiration(self):
        """Test a series of `enqueue_offload()` calls with `days_old` non-zero.

        This tests that offload works as expected if calls are made
        between finishing and expiration, and after the job expires.

        """
        self._job.set_finished(_TEST_EXPIRATION_AGE)
        self._offload_unexpired_job(_TEST_EXPIRATION_AGE)
        self._job.set_expired(_TEST_EXPIRATION_AGE)
        self._offload_expired_job(_TEST_EXPIRATION_AGE)

    def test_case_3_with_expiration(self):
        """Test a series of `enqueue_offload()` calls with `days_old` non-zero.

        This tests that offload works as expected if calls are made
        only before finishing and after expiration.

        """
        self._offload_unexpired_job(_TEST_EXPIRATION_AGE)
        self._job.set_expired(_TEST_EXPIRATION_AGE)
        self._offload_expired_job(_TEST_EXPIRATION_AGE)

    def test_case_4_with_expiration(self):
        """Test a series of `enqueue_offload()` calls with `days_old` non-zero.

        This tests that offload works as expected if calls are made
        only after expiration.

        """
        self._job.set_expired(_TEST_EXPIRATION_AGE)
        self._offload_expired_job(_TEST_EXPIRATION_AGE)


class GetJobDirectoriesTests(_TempResultsDirTestBase):
    """Tests for `_JobDirectory.get_job_directories()`."""

    def setUp(self):
        super(GetJobDirectoriesTests, self).setUp()
        self.make_job_hierarchy()
        os.mkdir('not-a-job')
        open('not-a-dir', 'w').close()

    def _run_get_directories(self, cls, expected_list):
        """Test `get_job_directories()` for the given class.

        Calls the method, and asserts that the returned list of
        directories matches the expected return value.

        @param expected_list Expected return value from the call.
        """
        dirlist = cls.get_job_directories()
        self.assertEqual(set(dirlist), set(expected_list))

    def test_get_regular_jobs(self):
        """Test `RegularJobDirectory.get_job_directories()`."""
        self._run_get_directories(job_directories.RegularJobDirectory,
                                  self.REGULAR_JOBLIST)

    def test_get_special_jobs(self):
        """Test `SpecialJobDirectory.get_job_directories()`."""
        self._run_get_directories(job_directories.SpecialJobDirectory,
                                  self.SPECIAL_JOBLIST)


class AddJobsTests(_TempResultsDirTestBase):
    """Tests for `Offloader._add_new_jobs()`."""

    MOREJOBS = ['115-fubar', '116-fubar', '117-fubar', '118-snafu']

    def setUp(self):
        super(AddJobsTests, self).setUp()
        self.make_job_hierarchy()
        self._offloader = gs_offloader.Offloader(_get_options(['-a']))

    def _check_open_jobs(self, expected_key_set):
        """Basic test assertions for `_add_new_jobs()`.

        Asserts the following:
          * The keys in the offloader's `_open_jobs` dictionary
            matches the expected set of keys.
          * For every job in `_open_jobs`, the job has the expected
            directory name.

        """
        self.assertEqual(expected_key_set,
                         set(self._offloader._open_jobs.keys()))
        for jobkey, job in self._offloader._open_jobs.items():
            self.assertEqual(jobkey, job._dirname)

    def test_add_jobs_empty(self):
        """Test adding jobs to an empty dictionary.

        Calls the offloader's `_add_new_jobs()`, then perform
        the assertions of `self._check_open_jobs()`.

        """
        self._offloader._add_new_jobs()
        self._check_open_jobs(set(self.REGULAR_JOBLIST) |
                              set(self.SPECIAL_JOBLIST))

    def test_add_jobs_non_empty(self):
        """Test adding jobs to a non-empty dictionary.

        Calls the offloader's `_add_new_jobs()` twice; once from
        initial conditions, and then again after adding more
        directories.  After the second call, perform the assertions
        of `self._check_open_jobs()`.  Additionally, assert that
        keys added by the first call still map to their original
        job object after the second call.

        """
        self._offloader._add_new_jobs()
        jobs_copy = self._offloader._open_jobs.copy()
        for d in self.MOREJOBS:
            os.mkdir(d)
        self._offloader._add_new_jobs()
        self._check_open_jobs(set(self.REGULAR_JOBLIST) |
                              set(self.SPECIAL_JOBLIST) |
                              set(self.MOREJOBS))
        for key in jobs_copy.keys():
            self.assertIs(jobs_copy[key],
                          self._offloader._open_jobs[key])


class JobStateTests(_TempResultsDirTestBase):
    """Tests for job state predicates.

    This tests for the expected results from the
    `is_offloaded()` and `is_reportable()` predicate
    methods.

    """

    def test_unfinished_job(self):
        """Test that an unfinished job reports the correct state.

        A job is "unfinished" if it isn't marked complete in the
        database.  A job in this state is neither "complete" nor
        "reportable".

        """
        job = self.make_job(self.REGULAR_JOBLIST[0])
        self.assertFalse(job.is_offloaded())
        self.assertFalse(job.is_reportable())

    def test_incomplete_job(self):
        """Test that an incomplete job reports the correct state.

        A job is "incomplete" if exactly one attempt has been made
        to offload the job, but its results directory still exists.
        A job in this state is neither "complete" nor "reportable".

        """
        job = self.make_job(self.REGULAR_JOBLIST[0])
        job.set_incomplete()
        self.assertFalse(job.is_offloaded())
        self.assertFalse(job.is_reportable())

    def test_reportable_job(self):
        """Test that a reportable job reports the correct state.

        A job is "reportable" if more than one attempt has been made
        to offload the job, and its results directory still exists.
        A job in this state is "reportable", but not "complete".

        """
        job = self.make_job(self.REGULAR_JOBLIST[0])
        job.set_reportable()
        self.assertFalse(job.is_offloaded())
        self.assertTrue(job.is_reportable())

    def test_completed_job(self):
        """Test that a completed job reports the correct state.

        A job is "completed" if at least one attempt has been made
        to offload the job, and its results directory still exists.
        A job in this state is "complete", and not "reportable".

        """
        job = self.make_job(self.REGULAR_JOBLIST[0])
        job.set_complete()
        self.assertTrue(job.is_offloaded())
        self.assertFalse(job.is_reportable())


class ReportingTests(_TempResultsDirTestBase):
    """Tests for `Offloader._update_offload_results()`."""

    def setUp(self):
        super(ReportingTests, self).setUp()
        self._offloader = gs_offloader.Offloader(_get_options([]))
        self.mox.StubOutWithMock(email_manager.manager,
                                 'send_email')

    def _add_job(self, jobdir):
        """Add a job to the dictionary of unfinished jobs."""
        j = self.make_job(jobdir)
        self._offloader._open_jobs[j._dirname] = j
        return j

    def _run_update_no_report(self, new_open_jobs):
        """Call `_update_offload_results()` expecting no report.

        Initial conditions are set up by the caller.  This calls
        `_update_offload_results()` once, and then checks these
        assertions:
          * The offloader's `_next_report_time` field is unchanged.
          * The offloader's new `_open_jobs` field contains only
            the entries in `new_open_jobs`.
          * The email_manager's `send_email` stub wasn't called.

        @param new_open_jobs A dictionary representing the expected
                             new value of the offloader's
                             `_open_jobs` field.
        """
        self.mox.ReplayAll()
        next_report_time = self._offloader._next_report_time
        self._offloader._update_offload_results()
        self.assertEqual(next_report_time,
                         self._offloader._next_report_time)
        self.assertEqual(self._offloader._open_jobs, new_open_jobs)
        self.mox.VerifyAll()
        self.mox.ResetAll()

    def _run_update_with_report(self, new_open_jobs):
        """Call `_update_offload_results()` expecting an e-mail report.

        Initial conditions are set up by the caller.  This calls
        `_update_offload_results()` once, and then checks these
        assertions:
          * The offloader's `_next_report_time` field is updated
            to an appropriate new time.
          * The offloader's new `_open_jobs` field contains only
            the entries in `new_open_jobs`.
          * The email_manager's `send_email` stub was called.

        @param new_open_jobs A dictionary representing the expected
                             new value of the offloader's
                             `_open_jobs` field.
        """
        email_manager.manager.send_email(
            mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg())
        self.mox.ReplayAll()
        t0 = time.time() + gs_offloader.REPORT_INTERVAL_SECS
        self._offloader._update_offload_results()
        t1 = time.time() + gs_offloader.REPORT_INTERVAL_SECS
        next_report_time = self._offloader._next_report_time
        self.assertGreaterEqual(next_report_time, t0)
        self.assertLessEqual(next_report_time, t1)
        self.assertEqual(self._offloader._open_jobs, new_open_jobs)
        self.mox.VerifyAll()
        self.mox.ResetAll()

    def test_no_jobs(self):
        """Test `_update_offload_results()` with no open jobs.

        Initial conditions are an empty `_open_jobs` list and
        `_next_report_time` in the past.  Expected result is no
        e-mail report, and an empty `_open_jobs` list.

        """
        self._run_update_no_report({})

    def test_all_completed(self):
        """Test `_update_offload_results()` with only complete jobs.

        Initial conditions are an `_open_jobs` list consisting of
        only completed jobs and `_next_report_time` in the past.
        Expected result is no e-mail report, and an empty
        `_open_jobs` list.

        """
        for d in self.REGULAR_JOBLIST:
            self._add_job(d).set_complete()
        self._run_update_no_report({})

    def test_none_finished(self):
        """Test `_update_offload_results()` with only unfinished jobs.

        Initial conditions are an `_open_jobs` list consisting of
        only unfinished jobs and `_next_report_time` in the past.
        Expected result is no e-mail report, and no change to the
        `_open_jobs` list.

        """
        for d in self.REGULAR_JOBLIST:
            self._add_job(d)
        self._run_update_no_report(self._offloader._open_jobs.copy())

    def test_none_reportable(self):
        """Test `_update_offload_results()` with only incomplete jobs.

        Initial conditions are an `_open_jobs` list consisting of
        only incomplete jobs and `_next_report_time` in the past.
        Expected result is no e-mail report, and no change to the
        `_open_jobs` list.

        """
        for d in self.REGULAR_JOBLIST:
            self._add_job(d).set_incomplete()
        self._run_update_no_report(self._offloader._open_jobs.copy())

    def test_report_not_ready(self):
        """Test `_update_offload_results()` e-mail throttling.

        Initial conditions are an `_open_jobs` list consisting of
        only reportable jobs but with `_next_report_time` in
        the future.  Expected result is no e-mail report, and no
        change to the `_open_jobs` list.

        """
        # N.B.  This test may fail if its run time exceeds more than
        # about _MARGIN_SECS seconds.
        for d in self.REGULAR_JOBLIST:
            self._add_job(d).set_reportable()
        self._offloader._next_report_time += _MARGIN_SECS
        self._run_update_no_report(self._offloader._open_jobs.copy())

    def test_reportable(self):
        """Test `_update_offload_results()` with reportable jobs.

        Initial conditions are an `_open_jobs` list consisting of
        only reportable jobs and with `_next_report_time` in
        the past.  Expected result is an e-mail report, and no
        change to the `_open_jobs` list.

        """
        for d in self.REGULAR_JOBLIST:
            self._add_job(d).set_reportable()
        self._run_update_with_report(self._offloader._open_jobs.copy())


if __name__ == '__main__':
    unittest.main()
