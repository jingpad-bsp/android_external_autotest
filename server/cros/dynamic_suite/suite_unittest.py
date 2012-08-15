#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


"""Unit tests for server/cros/dynamic_suite/dynamic_suite.py."""

import logging
import mox
import shutil
import tempfile
import unittest

from autotest_lib.client.common_lib import base_job, control_data
from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.server.cros.dynamic_suite import control_file_getter
from autotest_lib.server.cros.dynamic_suite import host_lock_manager, job_status
from autotest_lib.server.cros.dynamic_suite import tools
from autotest_lib.server.cros.dynamic_suite.comparitors import StatusContains
from autotest_lib.server.cros.dynamic_suite.suite import Suite
from autotest_lib.server.cros.dynamic_suite.fakes import FakeControlData
from autotest_lib.server.cros.dynamic_suite.fakes import FakeHost, FakeJob
from autotest_lib.server.cros.dynamic_suite.fakes import FakeLabel
from autotest_lib.server import frontend


class SuiteTest(mox.MoxTestBase):
    """Unit tests for dynamic_suite Suite class.

    @var _BUILD: fake build
    @var _TAG: fake suite tag
    """

    _BUILD = 'build'
    _TAG = 'suite_tag'


    def setUp(self):
        super(SuiteTest, self).setUp()
        self.afe = self.mox.CreateMock(frontend.AFE)
        self.tko = self.mox.CreateMock(frontend.TKO)

        self.tmpdir = tempfile.mkdtemp(suffix=type(self).__name__)

        self.manager = self.mox.CreateMock(host_lock_manager.HostLockManager)
        self.getter = self.mox.CreateMock(control_file_getter.ControlFileGetter)

        self.files = {'one': FakeControlData(self._TAG, 'data_one', expr=True),
                      'two': FakeControlData(self._TAG, 'data_two'),
                      'three': FakeControlData(self._TAG, 'data_three')}

        self.files_to_filter = {
            'with/deps/...': FakeControlData(self._TAG, 'gets filtered'),
            'with/profilers/...': FakeControlData(self._TAG, 'gets filtered')}


    def tearDown(self):
        super(SuiteTest, self).tearDown()
        shutil.rmtree(self.tmpdir, ignore_errors=True)


    def expect_control_file_parsing(self):
        """Expect an attempt to parse the 'control files' in |self.files|."""
        all_files = self.files.keys() + self.files_to_filter.keys()
        self._set_control_file_parsing_expectations(False, all_files,
                                                    self.files.iteritems())


    def expect_control_file_reparsing(self):
        """Expect re-parsing the 'control files' in |self.files|."""
        all_files = self.files.keys() + self.files_to_filter.keys()
        self._set_control_file_parsing_expectations(True, all_files,
                                                    self.files.iteritems())


    def expect_racy_control_file_reparsing(self, new_files):
        """Expect re-fetching and parsing of control files to return extra.

        @param new_files: extra control files that showed up during scheduling.
        """
        all_files = (self.files.keys() + self.files_to_filter.keys() +
                     new_files.keys())
        new_files.update(self.files)
        self._set_control_file_parsing_expectations(True, all_files,
                                                    new_files.iteritems())


    def _set_control_file_parsing_expectations(self, already_stubbed,
                                               file_list, files_to_parse):
        """Expect an attempt to parse the 'control files' in |files|.

        @param already_stubbed: parse_control_string already stubbed out.
        @param file_list: the files the dev server returns
        @param files_to_parse: the {'name': FakeControlData} dict of files we
                               expect to get parsed.
        """
        if not already_stubbed:
            self.mox.StubOutWithMock(control_data, 'parse_control_string')

        self.getter.get_control_file_list().AndReturn(file_list)
        for file, data in files_to_parse:
            self.getter.get_control_file_contents(
                file).InAnyOrder().AndReturn(data.string)
            control_data.parse_control_string(
                data.string, raise_warnings=True).InAnyOrder().AndReturn(data)


    def testFindAndParseStableTests(self):
        """Should find only non-experimental tests that match a predicate."""
        self.expect_control_file_parsing()
        self.mox.ReplayAll()

        predicate = lambda d: d.text == self.files['two'].string
        tests = Suite.find_and_parse_tests(self.getter, predicate)
        self.assertEquals(len(tests), 1)
        self.assertEquals(tests[0], self.files['two'])


    def testFindAndParseTests(self):
        """Should find all tests that match a predicate."""
        self.expect_control_file_parsing()
        self.mox.ReplayAll()

        predicate = lambda d: d.text != self.files['two'].string
        tests = Suite.find_and_parse_tests(self.getter,
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
        self.mox.StubOutWithMock(Suite, 'find_and_parse_tests')
        Suite.find_and_parse_tests(
            mox.IgnoreArg(),
            mox.IgnoreArg(),
            add_experimental=True).AndReturn(self.files.values())


    def testStableUnstableFilter(self):
        """Should distinguish between experimental and stable tests."""
        self.mock_control_file_parsing()
        self.mox.ReplayAll()
        suite = Suite.create_from_name(self._TAG, self.tmpdir,
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
                meta_hosts=[constants.VERSION_PREFIX + self._BUILD],
                dependencies=[],
                keyvals={'build': self._BUILD, 'suite': self._TAG}
                ).AndReturn(FakeJob())


    def testScheduleTests(self):
        """Should schedule stable and experimental tests with the AFE."""
        self.mock_control_file_parsing()
        self.expect_job_scheduling(add_experimental=True)

        self.mox.ReplayAll()
        suite = Suite.create_from_name(self._TAG, self._BUILD,
                                                     afe=self.afe, tko=self.tko)
        suite.schedule()


    def testScheduleTestsAndRecord(self):
        """Should schedule stable and experimental tests with the AFE."""
        self.mock_control_file_parsing()
        self.mox.ReplayAll()
        suite = Suite.create_from_name(self._TAG, self._BUILD,
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
        suite = Suite.create_from_name(self._TAG, self._BUILD,
                                       afe=self.afe, tko=self.tko)
        suite.schedule(add_experimental=False)


    def _createSuiteWithMockedTestsAndControlFiles(self):
        """Create a Suite, using mocked tests and control file contents.

        @return Suite object, after mocking out behavior needed to create it.
        """
        self.expect_control_file_parsing()
        self.mox.ReplayAll()
        suite = Suite.create_from_name(self._TAG, self._BUILD, self.getter,
                                       self.afe, self.tko)
        self.mox.ResetAll()
        return suite


    def schedule_and_expect_these_results(self, suite, results, recorder):
        self.mox.StubOutWithMock(suite, 'schedule')
        suite.schedule(True)
        self.manager.unlock()
        for result in results:
            status = result[0]
            test_name = result[1]
            recorder.record_entry(
                StatusContains.CreateFromStrings('START', test_name))
            recorder.record_entry(
                StatusContains.CreateFromStrings(*result)).InAnyOrder('results')
            recorder.record_entry(
                StatusContains.CreateFromStrings('END %s' % status, test_name))
        self.mox.StubOutWithMock(job_status, 'wait_for_results')
        job_status.wait_for_results(self.afe, self.tko, suite._jobs).AndReturn(
            map(lambda r: job_status.Status(*r), results))


    def testRunAndWaitSuccess(self):
        """Should record successful results."""
        suite = self._createSuiteWithMockedTestsAndControlFiles()

        recorder = self.mox.CreateMock(base_job.base_job)
        recorder.record_entry(
            StatusContains.CreateFromStrings('INFO', 'Start %s' % self._TAG))

        results = [('GOOD', 'good'), ('FAIL', 'bad', 'reason')]
        self.schedule_and_expect_these_results(suite, results, recorder)
        self.expect_control_file_reparsing()
        self.mox.ReplayAll()

        suite.run_and_wait(recorder.record_entry, self.manager, True)


    def testRunAndWaitFailure(self):
        """Should record failure to gather results."""
        suite = self._createSuiteWithMockedTestsAndControlFiles()

        recorder = self.mox.CreateMock(base_job.base_job)
        recorder.record_entry(
            StatusContains.CreateFromStrings('INFO', 'Start %s' % self._TAG))
        recorder.record_entry(
            StatusContains.CreateFromStrings('FAIL', self._TAG, 'waiting'))

        self.mox.StubOutWithMock(suite, 'schedule')
        suite.schedule(True)
        self.manager.unlock()
        self.mox.StubOutWithMock(job_status, 'wait_for_results')
        job_status.wait_for_results(mox.IgnoreArg(),
                                    mox.IgnoreArg(),
                                    mox.IgnoreArg()).AndRaise(
                                            Exception('Expected during test.'))
        self.expect_control_file_reparsing()
        self.mox.ReplayAll()

        suite.run_and_wait(recorder.record_entry, self.manager, True)


    def testRunAndWaitScheduleFailure(self):
        """Should record failure to schedule jobs."""
        suite = self._createSuiteWithMockedTestsAndControlFiles()

        recorder = self.mox.CreateMock(base_job.base_job)
        recorder.record_entry(
            StatusContains.CreateFromStrings('INFO', 'Start %s' % self._TAG))
        recorder.record_entry(
            StatusContains.CreateFromStrings('FAIL', self._TAG, 'scheduling'))

        self.mox.StubOutWithMock(suite, 'schedule')
        suite.schedule(True).AndRaise(Exception('Expected during test.'))
        self.expect_control_file_reparsing()
        self.mox.ReplayAll()

        suite.run_and_wait(recorder.record_entry, self.manager, True)


    def testRunAndWaitDevServerRacyFailure(self):
        """Should record discovery of dev server races in listing files."""
        suite = self._createSuiteWithMockedTestsAndControlFiles()

        recorder = self.mox.CreateMock(base_job.base_job)
        recorder.record_entry(
            StatusContains.CreateFromStrings('INFO', 'Start %s' % self._TAG))

        results = [('GOOD', 'good'), ('FAIL', 'bad', 'reason')]
        self.schedule_and_expect_these_results(suite, results, recorder)

        self.expect_racy_control_file_reparsing(
            {'new': FakeControlData(self._TAG, '!')})

        recorder.record_entry(
            StatusContains.CreateFromStrings('FAIL', self._TAG, 'Dev Server'))
        self.mox.ReplayAll()

        suite.run_and_wait(recorder.record_entry, self.manager, True)
