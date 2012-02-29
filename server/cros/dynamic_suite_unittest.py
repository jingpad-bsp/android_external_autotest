#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for server/cros/dynamic_suite.py."""

import logging
import mox
import shutil
import tempfile
import time
import unittest

from autotest_lib.client.common_lib import base_job, control_data, global_config
from autotest_lib.server.cros import control_file_getter, dynamic_suite
from autotest_lib.server import frontend

class FakeJob(object):
    """Faked out RPC-client-side Job object."""
    def __init__(self, id=0, statuses=[]):
        self.id = id
        self.owner = 'tester'
        self.name = 'Fake Job %d' % self.id
        self.statuses = statuses


class ReimagerTest(mox.MoxTestBase):
    """Unit tests for dynamic_suite.Reimager.

    @var _URL: fake image url
    @var _BUILD: fake build
    @var _NUM: fake number of machines to run on
    @var _BOARD: fake board to reimage
    """

    _URL = 'http://nothing/%s'
    _BUILD = 'build'
    _NUM = 4
    _BOARD = 'board'
    _CONFIG = global_config.global_config


    def setUp(self):
        super(ReimagerTest, self).setUp()
        self.afe = self.mox.CreateMock(frontend.AFE)
        self.tko = self.mox.CreateMock(frontend.TKO)
        self.reimager = dynamic_suite.Reimager('', afe=self.afe, tko=self.tko)
        self._CONFIG.override_config_value('CROS',
                                           'sharding_factor',
                                           "%d" % self._NUM)


    def testEnsureVersionLabelAlreadyExists(self):
        """Should not create a label if it already exists."""
        name = 'label'
        self.afe.get_labels(name=name).AndReturn([name])
        self.mox.ReplayAll()
        self.reimager._ensure_version_label(name)


    def testEnsureVersionLabel(self):
        """Should create a label if it doesn't already exist."""
        name = 'label'
        self.afe.get_labels(name=name).AndReturn([])
        self.afe.create_label(name=name)
        self.mox.ReplayAll()
        self.reimager._ensure_version_label(name)


    def testInjectVars(self):
        """Should inject dict of varibles into provided strings."""
        def find_all_in(d, s):
            """Returns true if all key-value pairs in |d| are printed in |s|."""
            return reduce(lambda b,i: "%s='%s'\n" % i in s, d.iteritems(), True)

        v = {'v1': 'one', 'v2': 'two'}
        self.assertTrue(find_all_in(v, dynamic_suite.inject_vars(v, '')))
        self.assertTrue(find_all_in(v, dynamic_suite.inject_vars(v, 'ctrl')))


    def testReportResultsGood(self):
        """Should report results in the case where all jobs passed."""
        job = self.mox.CreateMock(frontend.Job)
        job.name = 'RPC Client job'
        job.result = True
        recorder = self.mox.CreateMock(base_job.base_job)
        recorder.record('GOOD', mox.IgnoreArg(), job.name)
        self.mox.ReplayAll()
        self.reimager._report_results(job, recorder.record)


    def testReportResultsBad(self):
        """Should report results in various job failure cases.

        In this test scenario, there are five hosts, all the 'netbook' platform.

        h1: Did not run
        h2: Two failed tests
        h3: Two aborted tests
        h4: completed, GOOD
        h5: completed, GOOD
        """
        H1 = 'host1'
        H2 = 'host2'
        H3 = 'host3'
        H4 = 'host4'
        H5 = 'host5'

        class FakeResult(object):
            def __init__(self, reason):
                self.reason = reason


        # The RPC-client-side Job object that is annotated with results.
        job = FakeJob()
        job.result = None  # job failed, there are results to report.

        # The semantics of |results_platform_map| and |test_results| are
        # drawn from frontend.AFE.poll_all_jobs()
        job.results_platform_map = {'netbook': {'Aborted' : [H3],
                                                'Completed' : [H1, H4, H5],
                                                'Failed':     [H2]
                                                }
                                    }
        # Gin up fake results for H2 and H3 failure cases.
        h2 = frontend.TestResults()
        h2.fail = [FakeResult('a'), FakeResult('b')]
        h3 = frontend.TestResults()
        h3.fail = [FakeResult('a'), FakeResult('b')]
        # Skipping H1 in |test_status| dict means that it did not get run.
        job.test_status = {H2: h2, H3: h3, H4: {}, H5: {}}

        # Set up recording expectations.
        rjob = self.mox.CreateMock(base_job.base_job)
        for res in h2.fail:
            rjob.record('FAIL', mox.IgnoreArg(), H2, res.reason).InAnyOrder()
        for res in h3.fail:
            rjob.record('ABORT', mox.IgnoreArg(), H3, res.reason).InAnyOrder()
        rjob.record('GOOD', mox.IgnoreArg(), H4).InAnyOrder()
        rjob.record('GOOD', mox.IgnoreArg(), H5).InAnyOrder()
        rjob.record(
            'ERROR', mox.IgnoreArg(), H1, mox.IgnoreArg()).InAnyOrder()

        self.mox.ReplayAll()
        self.reimager._report_results(job, rjob.record)


    def testScheduleJob(self):
        """Should be able to create a job with the AFE."""
        # Fake out getting the autoupdate control file contents.
        cf_getter = self.mox.CreateMock(control_file_getter.ControlFileGetter)
        cf_getter.get_control_file_contents_by_name('autoupdate').AndReturn('')
        self.reimager._cf_getter = cf_getter

        self._CONFIG.override_config_value('CROS',
                                           'image_url_pattern',
                                           self._URL)
        self.afe.create_job(
            control_file=mox.And(mox.StrContains(self._BUILD),
                                 mox.StrContains(self._URL % self._BUILD)),
            name=mox.StrContains(self._BUILD),
            control_type='Server',
            meta_hosts=['board:'+self._BOARD] * self._NUM,
            dependencies=[])
        self.mox.ReplayAll()
        self.reimager._schedule_reimage_job(self._BUILD, self._NUM, self._BOARD)


    def expect_attempt(self, success, ex=None):
        """Sets up |self.reimager| to expect an attempt() that returns |success|

        @param success: the value returned by poll_job_results()
        @param ex: if not None, |ex| is raised by get_jobs()
        @return a FakeJob configured with appropriate expectations
        """
        canary = FakeJob()
        self.mox.StubOutWithMock(self.reimager, '_ensure_version_label')
        self.reimager._ensure_version_label(mox.StrContains(self._BUILD))

        self.mox.StubOutWithMock(self.reimager, '_schedule_reimage_job')
        self.reimager._schedule_reimage_job(self._BUILD,
                                            self._NUM,
                                            self._BOARD).AndReturn(canary)
        if success is not None:
            self.mox.StubOutWithMock(self.reimager, '_report_results')
            self.reimager._report_results(canary, mox.IgnoreArg())

        self.afe.get_jobs(id=canary.id, not_yet_run=True).AndReturn([])
        if ex is not None:
            self.afe.get_jobs(id=canary.id, finished=True).AndRaise(ex)
        else:
            self.afe.get_jobs(id=canary.id, finished=True).AndReturn([canary])
            self.afe.poll_job_results(mox.IgnoreArg(),
                                      canary, 0).AndReturn(success)

        return canary


    def testSuccessfulReimage(self):
        """Should attempt a reimage and record success."""
        canary = self.expect_attempt(True)

        rjob = self.mox.CreateMock(base_job.base_job)
        rjob.record('START', mox.IgnoreArg(), mox.IgnoreArg())
        rjob.record('END GOOD', mox.IgnoreArg(), mox.IgnoreArg())
        self.mox.ReplayAll()
        self.reimager.attempt(self._BUILD, self._BOARD, rjob.record)


    def testFailedReimage(self):
        """Should attempt a reimage and record failure."""
        canary = self.expect_attempt(False)

        rjob = self.mox.CreateMock(base_job.base_job)
        rjob.record('START', mox.IgnoreArg(), mox.IgnoreArg())
        rjob.record('END FAIL', mox.IgnoreArg(), mox.IgnoreArg())
        self.mox.ReplayAll()
        self.reimager.attempt(self._BUILD, self._BOARD, rjob.record)


    def testReimageThatNeverHappened(self):
        """Should attempt a reimage and record that it didn't run."""
        canary = self.expect_attempt(None)

        rjob = self.mox.CreateMock(base_job.base_job)
        rjob.record('START', mox.IgnoreArg(), mox.IgnoreArg())
        rjob.record('FAIL', mox.IgnoreArg(), canary.name, mox.IgnoreArg())
        rjob.record('END FAIL', mox.IgnoreArg(), mox.IgnoreArg())
        self.mox.ReplayAll()
        self.reimager.attempt(self._BUILD, self._BOARD, rjob.record)


    def testReimageThatRaised(self):
        """Should attempt a reimage that raises an exception and record that."""
        ex_message = 'Oh no!'
        canary = self.expect_attempt(None, Exception(ex_message))

        rjob = self.mox.CreateMock(base_job.base_job)
        rjob.record('START', mox.IgnoreArg(), mox.IgnoreArg())
        rjob.record('END ERROR', mox.IgnoreArg(), mox.IgnoreArg(), ex_message)
        self.mox.ReplayAll()
        self.reimager.attempt(self._BUILD, self._BOARD, rjob.record)


class SuiteTest(mox.MoxTestBase):
    """Unit tests for dynamic_suite.Suite.

    @var _BUILD: fake build
    @var _TAG: fake suite tag
    """

    _BUILD = 'build'
    _TAG = 'suite_tag'


    def setUp(self):
        class FakeControlData(object):
            """A fake parsed control file data structure."""
            def __init__(self, data, expr=False):
                self.string = 'text-' + data
                self.name = 'name-' + data
                self.data = data
                self.test_type = 'Client'
                self.experimental = expr


        super(SuiteTest, self).setUp()
        self.afe = self.mox.CreateMock(frontend.AFE)
        self.tko = self.mox.CreateMock(frontend.TKO)

        self.tmpdir = tempfile.mkdtemp(suffix=type(self).__name__)

        self.getter = self.mox.CreateMock(control_file_getter.ControlFileGetter)

        self.files = {'one': FakeControlData('data_one', expr=True),
                      'two': FakeControlData('data_two'),
                      'three': FakeControlData('data_three')}


    def tearDown(self):
        super(SuiteTest, self).tearDown()
        shutil.rmtree(self.tmpdir, ignore_errors=True)


    def expect_control_file_parsing(self):
        """Expect an attempt to parse the 'control files' in |self.files|."""
        self.getter.get_control_file_list().AndReturn(self.files.keys())
        self.mox.StubOutWithMock(control_data, 'parse_control_string')
        for file, data in self.files.iteritems():
            self.getter.get_control_file_contents(file).AndReturn(data.string)
            control_data.parse_control_string(
                data.string, raise_warnings=True).AndReturn(data)


    def testFindAndParseStableTests(self):
        """Should find only non-experimental tests that match a predicate."""
        self.expect_control_file_parsing()
        self.mox.ReplayAll()

        predicate = lambda d: d.text == self.files['two'].string
        tests = dynamic_suite.Suite.find_and_parse_tests(self.getter, predicate)
        self.assertEquals(len(tests), 1)
        self.assertEquals(tests[0], self.files['two'])


    def testFindAndParseTests(self):
        """Should find all tests that match a predicate."""
        self.expect_control_file_parsing()
        self.mox.ReplayAll()

        predicate = lambda d: d.text != self.files['two'].string
        tests = dynamic_suite.Suite.find_and_parse_tests(self.getter,
                                                         predicate,
                                                         add_experimental=True)
        self.assertEquals(len(tests), 2)
        self.assertTrue(self.files['one'] in tests)
        self.assertTrue(self.files['three'] in tests)


    def mock_control_file_parsing(self):
        """Fake out find_and_parse_tests(), returning content from |self.files|.
        """
        for test in self.files.values():
            test.text = test.string  # mimic parsing.
        self.mox.StubOutWithMock(dynamic_suite.Suite, 'find_and_parse_tests')
        dynamic_suite.Suite.find_and_parse_tests(
            mox.IgnoreArg(),
            mox.IgnoreArg(),
            add_experimental=True).AndReturn(self.files.values())


    def testStableUnstableFilter(self):
        """Should distinguish between experimental and stable tests."""
        self.mock_control_file_parsing()
        self.mox.ReplayAll()
        suite = dynamic_suite.Suite.create_from_name(self._TAG, self.tmpdir,
                                                     afe=self.afe, tko=self.tko)

        self.assertTrue(self.files['one'] in suite.tests)
        self.assertTrue(self.files['two'] in suite.tests)
        self.assertTrue(self.files['one'] in suite.unstable_tests())
        self.assertTrue(self.files['two'] in suite.stable_tests())
        self.assertFalse(self.files['one'] in suite.stable_tests())
        self.assertFalse(self.files['two'] in suite.unstable_tests())


    def expect_job_scheduling(self, add_experimental):
        """Expect jobs to be scheduled for 'tests' in |self.files|.

        @param add_experimental: expect jobs for experimental tests as well.
        """
        for test in self.files.values():
            if not add_experimental and test.experimental:
                continue
            self.afe.create_job(
                control_file=test.text,
                name=mox.And(mox.StrContains(self._BUILD),
                             mox.StrContains(test.name)),
                control_type=mox.IgnoreArg(),
                meta_hosts=[dynamic_suite.VERSION_PREFIX + self._BUILD],
                dependencies=[]).AndReturn(FakeJob())


    def testScheduleTests(self):
        """Should schedule stable and experimental tests with the AFE."""
        self.mock_control_file_parsing()
        self.expect_job_scheduling(add_experimental=True)

        self.mox.ReplayAll()
        suite = dynamic_suite.Suite.create_from_name(self._TAG, self._BUILD,
                                                     afe=self.afe, tko=self.tko)
        suite.schedule()


    def testScheduleTestsAndRecord(self):
        """Should schedule stable and experimental tests with the AFE."""
        self.mock_control_file_parsing()
        self.mox.ReplayAll()
        suite = dynamic_suite.Suite.create_from_name(self._TAG, self._BUILD,
                                                     afe=self.afe, tko=self.tko,
                                                     results_dir=self.tmpdir)
        self.mox.ResetAll()
        self.expect_job_scheduling(add_experimental=True)
        self.mox.StubOutWithMock(suite, '_record_scheduled_jobs')
        suite._record_scheduled_jobs()
        self.mox.ReplayAll()
        suite.schedule()
        for job in  suite._jobs:
          self.assertTrue(hasattr(job, 'test_name'))


    def testScheduleStableTests(self):
        """Should schedule only stable tests with the AFE."""
        self.mock_control_file_parsing()
        self.expect_job_scheduling(add_experimental=False)

        self.mox.ReplayAll()
        suite = dynamic_suite.Suite.create_from_name(self._TAG, self._BUILD,
                                                     afe=self.afe, tko=self.tko)
        suite.schedule(add_experimental=False)


    def expect_result_gathering(self, job):
        self.afe.get_jobs(id=job.id, finished=True).AndReturn(job)
        entries = map(lambda s: s.entry, job.statuses)
        self.afe.run('get_host_queue_entries',
                     job=job.id).AndReturn(entries)
        if True not in map(lambda e: 'aborted' in e and e['aborted'], entries):
            self.tko.get_status_counts(job=job.id).AndReturn(job.statuses)


    def _createSuiteWithMockedTestsAndControlFiles(self):
        """Create a Suite, using mocked tests and control file contents.

        @return Suite object, after mocking out behavior needed to create it.
        """
        self.expect_control_file_parsing()
        self.mox.ReplayAll()
        suite = dynamic_suite.Suite.create_from_name(self._TAG, self._BUILD,
                                                     self.getter, self.afe,
                                                     self.tko)
        self.mox.ResetAll()
        return suite


    def testWaitForResults(self):
        """Should gather status and return records for job summaries."""
        class FakeStatus(object):
            """Fake replacement for server-side job status objects.

            @var status: 'GOOD', 'FAIL', 'ERROR', etc.
            @var test_name: name of the test this is status for
            @var reason: reason for failure, if any
            @var aborted: present and True if the job was aborted.  Optional.
            """
            def __init__(self, code, name, reason, aborted=None):
                self.status = code
                self.test_name = name
                self.reason = reason
                self.entry = {}
                if aborted:
                    self.entry['aborted'] = True

            def equals_record(self, args):
                """Compares this object to a recorded status."""
                return self._equals_record(*args)

            def _equals_record(self, status, subdir, name, reason=None):
                """Compares this object and fields of recorded status."""
                if 'aborted' in self.entry and self.entry['aborted']:
                    return status == 'ABORT'
                return (self.status == status and
                        self.test_name == name and
                        self.reason == reason)

        suite = self._createSuiteWithMockedTestsAndControlFiles()

        jobs = [FakeJob(0, [FakeStatus('GOOD', 'T0', ''),
                            FakeStatus('GOOD', 'T1', '')]),
                FakeJob(1, [FakeStatus('ERROR', 'T0', 'err', False),
                            FakeStatus('GOOD', 'T1', '')]),
                FakeJob(2, [FakeStatus('TEST_NA', 'T0', 'no')]),
                FakeJob(2, [FakeStatus('FAIL', 'T0', 'broken')]),
                FakeJob(3, [FakeStatus('ERROR', 'T0', 'gah', True)])]
        # To simulate a job that isn't ready the first time we check.
        self.afe.get_jobs(id=jobs[0].id, finished=True).AndReturn([])
        # Expect all the rest of the jobs to be good to go the first time.
        for job in jobs[1:]:
            self.expect_result_gathering(job)
        # Then, expect job[0] to be ready.
        self.expect_result_gathering(jobs[0])
        # Expect us to poll twice.
        self.mox.StubOutWithMock(time, 'sleep')
        time.sleep(5)
        time.sleep(5)
        self.mox.ReplayAll()

        suite._jobs = list(jobs)
        results = [result for result in suite.wait_for_results()]
        for job in jobs:
            for status in job.statuses:
                self.assertTrue(True in map(status.equals_record, results))


    def testRunAndWaitSuccess(self):
        """Should record successful results."""
        suite = self._createSuiteWithMockedTestsAndControlFiles()

        results = [('GOOD', None, 'good'), ('FAIL', None, 'bad', 'reason')]
        recorder = self.mox.CreateMock(base_job.base_job)
        recorder.record('INFO', None, 'Start %s' % self._TAG)
        for result in results:
            status = result[0]
            test_name = result[2]
            recorder.record('START', None, test_name)
            recorder.record(*result).InAnyOrder('results')
            recorder.record('END %s' % status, None, test_name)

        self.mox.StubOutWithMock(suite, 'schedule')
        suite.schedule(True)
        self.mox.StubOutWithMock(suite, 'wait_for_results')
        suite.wait_for_results().AndReturn(results)
        self.mox.ReplayAll()

        suite.run_and_wait(recorder.record, True)


    def testRunAndWaitFailure(self):
        """Should record failure to gather results."""
        suite = self._createSuiteWithMockedTestsAndControlFiles()

        recorder = self.mox.CreateMock(base_job.base_job)
        recorder.record('INFO', None, 'Start %s' % self._TAG)
        recorder.record('FAIL', None, self._TAG,
                        mox.StrContains('waiting'))

        self.mox.StubOutWithMock(suite, 'schedule')
        suite.schedule(True)
        self.mox.StubOutWithMock(suite, 'wait_for_results')
        suite.wait_for_results().AndRaise(Exception())
        self.mox.ReplayAll()

        suite.run_and_wait(recorder.record, True)


    def testRunAndWaitScheduleFailure(self):
        """Should record failure to schedule jobs."""
        suite = self._createSuiteWithMockedTestsAndControlFiles()

        recorder = self.mox.CreateMock(base_job.base_job)
        recorder.record('INFO', None, 'Start %s' % self._TAG)
        recorder.record('FAIL', None, self._TAG,
                        mox.StrContains('scheduling'))

        self.mox.StubOutWithMock(suite, 'schedule')
        suite.schedule(True).AndRaise(Exception())
        self.mox.ReplayAll()

        suite.run_and_wait(recorder.record, True)


if __name__ == '__main__':
  unittest.main()
