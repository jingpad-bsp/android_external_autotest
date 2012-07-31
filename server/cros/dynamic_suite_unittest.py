#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for server/cros/dynamic_suite.py."""

import logging
import mox
import random
import shutil
import tempfile
import time
import unittest

from autotest_lib.client.common_lib import base_job, control_data, error
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.frontend.afe.json_rpc import proxy
from autotest_lib.server.cros import control_file_getter, dynamic_suite
from autotest_lib.server.cros import host_lock_manager, job_status
from autotest_lib.server.cros.dynamic_suite_fakes import FakeControlData
from autotest_lib.server.cros.dynamic_suite_fakes import FakeHost, FakeJob
from autotest_lib.server.cros.dynamic_suite_fakes import FakeLabel
from autotest_lib.server import frontend


class StatusContains(mox.Comparator):
    @staticmethod
    def CreateFromStrings(status=None, test_name=None, reason=None):
        status_comp = mox.StrContains(status) if status else mox.IgnoreArg()
        name_comp = mox.StrContains(test_name) if test_name else mox.IgnoreArg()
        reason_comp = mox.StrContains(reason) if reason else mox.IgnoreArg()
        return StatusContains(status_comp, name_comp, reason_comp)


    def __init__(self, status=mox.IgnoreArg(), test_name=mox.IgnoreArg(),
                 reason=mox.IgnoreArg()):
        """Initialize.

        Takes mox.Comparator objects to apply to dynamic_suite.Status
        member variables.

        @param status: status code, e.g. 'INFO', 'START', etc.
        @param test_name: expected test name.
        @param reason: expected reason
        """
        self._status = status
        self._test_name = test_name
        self._reason = reason


    def equals(self, rhs):
        """Check to see if fields match base_job.status_log_entry obj in rhs.

        @param rhs: base_job.status_log_entry object to match.
        @return boolean
        """
        return (self._status.equals(rhs.status_code) and
                self._test_name.equals(rhs.operation) and
                self._reason.equals(rhs.message))


    def __repr__(self):
        return '<Status containing \'%s\t%s\t%s\'>' % (self._status,
                                                       self._test_name,
                                                       self._reason)


class DynamicSuiteTest(mox.MoxTestBase):
    """Unit tests for dynamic_suite module methods.

    @var _DARGS: default args to vet.
    """


    def setUp(self):
        super(DynamicSuiteTest, self).setUp()
        self._DARGS = {'name': 'name',
                       'build': 'build',
                       'board': 'board',
                       'job': self.mox.CreateMock(base_job.base_job),
                       'num': 1,
                       'pool': 'pool',
                       'skip_reimage': True,
                       'check_hosts': False,
                       'add_experimental': False}


    def testVetRequiredReimageAndRunArgs(self):
        """Should verify only that required args are present and correct."""
        build, board, name, job, _, _, _, _, _ = \
            dynamic_suite._vet_reimage_and_run_args(**self._DARGS)
        self.assertEquals(build, self._DARGS['build'])
        self.assertEquals(board, self._DARGS['board'])
        self.assertEquals(name, self._DARGS['name'])
        self.assertEquals(job, self._DARGS['job'])


    def testVetReimageAndRunBuildArgFail(self):
        """Should fail verification because |build| arg is bad."""
        self._DARGS['build'] = None
        self.assertRaises(error.SuiteArgumentException,
                          dynamic_suite._vet_reimage_and_run_args,
                          **self._DARGS)


    def testVetReimageAndRunBoardArgFail(self):
        """Should fail verification because |board| arg is bad."""
        self._DARGS['board'] = None
        self.assertRaises(error.SuiteArgumentException,
                          dynamic_suite._vet_reimage_and_run_args,
                          **self._DARGS)


    def testVetReimageAndRunNameArgFail(self):
        """Should fail verification because |name| arg is bad."""
        self._DARGS['name'] = None
        self.assertRaises(error.SuiteArgumentException,
                          dynamic_suite._vet_reimage_and_run_args,
                          **self._DARGS)


    def testVetReimageAndRunJobArgFail(self):
        """Should fail verification because |job| arg is bad."""
        self._DARGS['job'] = None
        self.assertRaises(error.SuiteArgumentException,
                          dynamic_suite._vet_reimage_and_run_args,
                          **self._DARGS)


    def testOverrideOptionalReimageAndRunArgs(self):
        """Should verify that optional args can be overridden."""
        _, _, _, _, pool, num, check, skip, expr = \
            dynamic_suite._vet_reimage_and_run_args(**self._DARGS)
        self.assertEquals(pool, self._DARGS['pool'])
        self.assertEquals(num, self._DARGS['num'])
        self.assertEquals(check, self._DARGS['check_hosts'])
        self.assertEquals(skip, self._DARGS['skip_reimage'])
        self.assertEquals(expr, self._DARGS['add_experimental'])


    def testDefaultOptionalReimageAndRunArgs(self):
        """Should verify that optional args get defaults."""
        del(self._DARGS['pool'])
        del(self._DARGS['skip_reimage'])
        del(self._DARGS['check_hosts'])
        del(self._DARGS['add_experimental'])
        del(self._DARGS['num'])
        _, _, _, _, pool, num, check, skip, expr = \
            dynamic_suite._vet_reimage_and_run_args(**self._DARGS)
        self.assertEquals(pool, None)
        self.assertEquals(num, None)
        self.assertEquals(check, True)
        self.assertEquals(skip, False)
        self.assertEquals(expr, True)


class ReimagerTest(mox.MoxTestBase):
    """Unit tests for dynamic_suite.Reimager.

    @var _URL: fake image url
    @var _BUILD: fake build
    @var _NUM: fake number of machines to run on
    @var _BOARD: fake board to reimage
    """

    _DEVSERVER_URL = 'http://nothing:8082'
    _URL = '%s/%s'
    _BUILD = 'build'
    _NUM = 4
    _BOARD = 'board'
    _CONFIG = global_config.global_config


    def setUp(self):
        super(ReimagerTest, self).setUp()
        self.afe = self.mox.CreateMock(frontend.AFE)
        self.tko = self.mox.CreateMock(frontend.TKO)
        self.manager = self.mox.CreateMock(host_lock_manager.HostLockManager)
        self.reimager = dynamic_suite.Reimager('', afe=self.afe, tko=self.tko)
        self._CONFIG.override_config_value('CROS',
                                           'sharding_factor',
                                           "%d" % self._NUM)


    def testEnsureVersionLabelAlreadyExists(self):
        """Should tolerate a label that already exists."""
        name = 'label'
        error = proxy.ValidationError(
            {'name': 'ValidationError',
             'message': '{"name": "This value must be unique"}',
             'traceback': ''},
            'BAD')
        self.afe.create_label(name=name).AndRaise(error)
        self.mox.ReplayAll()
        self.reimager._ensure_version_label(name)


    def testEnsureVersionLabel(self):
        """Should create a label if it doesn't already exist."""
        name = 'label'
        self.afe.create_label(name=name)
        self.mox.ReplayAll()
        self.reimager._ensure_version_label(name)


    def testCountHostsByBoardAndPool(self):
        """Should count available hosts by board and pool."""
        spec = [self._BOARD, 'pool:bvt']
        self.afe.get_hosts(multiple_labels=spec).AndReturn([FakeHost()])
        self.mox.ReplayAll()
        self.assertEquals(self.reimager._count_usable_hosts(spec), 1)


    def testCountHostsByBoard(self):
        """Should count available hosts by board."""
        spec = [self._BOARD]
        self.afe.get_hosts(multiple_labels=spec).AndReturn([FakeHost()] * 2)
        self.mox.ReplayAll()
        self.assertEquals(self.reimager._count_usable_hosts(spec), 2)


    def testCountZeroHostsByBoard(self):
        """Should count the available hosts, by board, getting zero."""
        spec = [self._BOARD]
        self.afe.get_hosts(multiple_labels=spec).AndReturn([])
        self.mox.ReplayAll()
        self.assertEquals(self.reimager._count_usable_hosts(spec), 0)


    def testInjectVars(self):
        """Should inject dict of varibles into provided strings."""
        def find_all_in(d, s):
            """Returns true if all key-value pairs in |d| are printed in |s|."""
            for k, v in d.iteritems():
                if isinstance(v, str):
                    if "%s='%s'\n" % (k, v) not in s:
                        return False
                else:
                    if "%s=%r\n" % (k, v) not in s:
                        return False
            return True

        v = {'v1': 'one', 'v2': 'two', 'v3': None, 'v4': False, 'v5': 5}
        self.assertTrue(find_all_in(v, dynamic_suite.inject_vars(v, '')))
        self.assertTrue(find_all_in(v, dynamic_suite.inject_vars(v, 'ctrl')))


    def testScheduleJob(self):
        """Should be able to create a job with the AFE."""
        # Fake out getting the autoupdate control file contents.
        cf_getter = self.mox.CreateMock(control_file_getter.ControlFileGetter)
        cf_getter.get_control_file_contents_by_name('autoupdate').AndReturn('')
        self.reimager._cf_getter = cf_getter
        self._CONFIG.override_config_value('CROS',
                                           'dev_server',
                                           self._DEVSERVER_URL)
        self._CONFIG.override_config_value('CROS',
                                           'image_url_pattern',
                                           self._URL)
        self.afe.create_job(
            control_file=mox.And(
                mox.StrContains(self._BUILD),
                mox.StrContains(self._URL % (self._DEVSERVER_URL,
                                             self._BUILD))),
            name=mox.StrContains(self._BUILD),
            control_type='Server',
            meta_hosts=[self._BOARD] * self._NUM,
            dependencies=[],
            priority='Low')
        self.mox.ReplayAll()
        self.reimager._schedule_reimage_job(self._BUILD, self._BOARD, None,
                                            self._NUM)

    def testPackageUrl(self):
        """Should be able to get the package_url for any build."""
        self._CONFIG.override_config_value('CROS',
                                           'dev_server',
                                           self._DEVSERVER_URL)
        self._CONFIG.override_config_value('CROS',
                                           'package_url_pattern',
                                           self._URL)
        self.mox.ReplayAll()
        package_url = dynamic_suite.get_package_url(self._BUILD)
        self.assertEqual(package_url, self._URL % (self._DEVSERVER_URL,
                                                   self._BUILD))

    def expect_attempt(self, canary_job, statuses, ex=None, check_hosts=True):
        """Sets up |self.reimager| to expect an attempt() that returns |success|

        Also stubs out Reimager._clear_build_state(), should the caller wish
        to set an expectation there as well.

        @param canary_job: a FakeJob representing the job we're expecting.
        @param statuses: dict mapping a hostname to its job_status.Status.
                         Will be returned by job_status.gather_per_host_results
        @param ex: if not None, |ex| is raised by get_jobs()
        @return a FakeJob configured with appropriate expectations
        """
        self.mox.StubOutWithMock(self.reimager, '_ensure_version_label')
        self.mox.StubOutWithMock(self.reimager, '_schedule_reimage_job')
        self.mox.StubOutWithMock(self.reimager, '_count_usable_hosts')
        self.mox.StubOutWithMock(self.reimager, '_clear_build_state')

        self.mox.StubOutWithMock(job_status, 'wait_for_jobs_to_start')
        self.mox.StubOutWithMock(job_status, 'wait_for_and_lock_job_hosts')
        self.mox.StubOutWithMock(job_status, 'gather_job_hostnames')
        self.mox.StubOutWithMock(job_status, 'wait_for_jobs_to_finish')
        self.mox.StubOutWithMock(job_status, 'gather_per_host_results')
        self.mox.StubOutWithMock(job_status, 'record_and_report_results')

        self.reimager._ensure_version_label(mox.StrContains(self._BUILD))
        self.reimager._schedule_reimage_job(self._BUILD,
                                            self._BOARD,
                                            None,
                                            self._NUM).AndReturn(canary_job)
        if check_hosts:
            self.reimager._count_usable_hosts(
                mox.IgnoreArg()).AndReturn(self._NUM)

        job_status.wait_for_jobs_to_start(self.afe, [canary_job])
        job_status.wait_for_and_lock_job_hosts(
            self.afe, [canary_job], self.manager).AndReturn(statuses.keys())

        if ex:
            job_status.wait_for_jobs_to_finish(self.afe,
                                               [canary_job]).AndRaise(ex)
        else:
            job_status.wait_for_jobs_to_finish(self.afe, [canary_job])
            job_status.gather_per_host_results(
                    mox.IgnoreArg(), mox.IgnoreArg(), [canary_job],
                    mox.StrContains(dynamic_suite.REIMAGE_JOB_NAME)).AndReturn(
                            statuses)

        if statuses:
            ret_val = reduce(lambda v, s: v and s.is_good(),
                             statuses.values(), True)
            job_status.record_and_report_results(
                statuses.values(), mox.IgnoreArg()).AndReturn(ret_val)


    def testSuccessfulReimage(self):
        """Should attempt a reimage and record success."""
        canary = FakeJob()
        statuses = {canary.hostnames[0]: job_status.Status('GOOD',
                                                           canary.hostnames[0])}
        self.expect_attempt(canary, statuses)

        rjob = self.mox.CreateMock(base_job.base_job)
        self.reimager._clear_build_state(mox.StrContains(canary.hostnames[0]))
        self.mox.ReplayAll()
        self.assertTrue(self.reimager.attempt(self._BUILD, self._BOARD, None,
                                              rjob.record_entry, True,
                                              self.manager))
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testFailedReimage(self):
        """Should attempt a reimage and record failure."""
        canary = FakeJob()
        statuses = {canary.hostnames[0]: job_status.Status('FAIL',
                                                           canary.hostnames[0])}
        self.expect_attempt(canary, statuses)

        rjob = self.mox.CreateMock(base_job.base_job)
        self.reimager._clear_build_state(mox.StrContains(canary.hostnames[0]))
        self.mox.ReplayAll()
        self.assertFalse(self.reimager.attempt(self._BUILD, self._BOARD, None,
                                               rjob.record_entry, True,
                                               self.manager))
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testReimageThatNeverHappened(self):
        """Should attempt a reimage and record that it didn't run."""
        canary = FakeJob()
        statuses = {'hostless': job_status.Status('ABORT', 'big_job_name')}
        self.expect_attempt(canary, statuses)

        rjob = self.mox.CreateMock(base_job.base_job)
        self.mox.ReplayAll()
        self.reimager.attempt(self._BUILD, self._BOARD, None,
                              rjob.record_entry, True, self.manager)
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testReimageThatRaised(self):
        """Should attempt a reimage that raises an exception and record that."""
        canary = FakeJob()
        ex_message = 'Oh no!'
        self.expect_attempt(canary, statuses={}, ex=Exception(ex_message))

        rjob = self.mox.CreateMock(base_job.base_job)
        rjob.record_entry(StatusContains.CreateFromStrings('START'))
        rjob.record_entry(StatusContains.CreateFromStrings('ERROR',
                                                           reason=ex_message))
        rjob.record_entry(StatusContains.CreateFromStrings('END ERROR'))
        self.mox.ReplayAll()
        self.reimager.attempt(self._BUILD, self._BOARD, None,
                              rjob.record_entry, True, self.manager)
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testSuccessfulReimageThatCouldNotScheduleRightAway(self):
        """Should attempt reimage, ignoring host availability; record success.
        """
        canary = FakeJob()
        statuses = {canary.hostnames[0]: job_status.Status('GOOD',
                                                           canary.hostnames[0])}
        self.expect_attempt(canary, statuses, check_hosts=False)

        rjob = self.mox.CreateMock(base_job.base_job)
        self.reimager._clear_build_state(mox.StrContains(canary.hostnames[0]))
        self.mox.ReplayAll()
        self.assertTrue(self.reimager.attempt(self._BUILD, self._BOARD, None,
                                              rjob.record_entry, False,
                                              self.manager))
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testReimageThatCouldNotSchedule(self):
        """Should attempt a reimage that can't be scheduled."""
        self.mox.StubOutWithMock(self.reimager, '_ensure_version_label')
        self.reimager._ensure_version_label(mox.StrContains(self._BUILD))

        self.mox.StubOutWithMock(self.reimager, '_count_usable_hosts')
        self.reimager._count_usable_hosts(mox.IgnoreArg()).AndReturn(1)

        rjob = self.mox.CreateMock(base_job.base_job)
        rjob.record_entry(StatusContains.CreateFromStrings('START'))
        rjob.record_entry(
            StatusContains.CreateFromStrings('WARN', reason='Too few hosts'))
        rjob.record_entry(StatusContains.CreateFromStrings('END WARN'))
        self.mox.ReplayAll()
        self.reimager.attempt(self._BUILD, self._BOARD, None,
                              rjob.record_entry, True, self.manager)
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testReimageWithNoAvailableHosts(self):
        """Should attempt a reimage while all hosts are dead."""
        self.mox.StubOutWithMock(self.reimager, '_ensure_version_label')
        self.reimager._ensure_version_label(mox.StrContains(self._BUILD))

        self.mox.StubOutWithMock(self.reimager, '_count_usable_hosts')
        self.reimager._count_usable_hosts(mox.IgnoreArg()).AndReturn(0)

        rjob = self.mox.CreateMock(base_job.base_job)
        rjob.record_entry(StatusContains.CreateFromStrings('START'))
        rjob.record_entry(StatusContains.CreateFromStrings('ERROR',
                                                           reason='All hosts'))
        rjob.record_entry(StatusContains.CreateFromStrings('END ERROR'))
        self.mox.ReplayAll()
        self.reimager.attempt(self._BUILD, self._BOARD, None,
                              rjob.record_entry, True, self.manager)
        self.reimager.clear_reimaged_host_state(self._BUILD)


class SuiteTest(mox.MoxTestBase):
    """Unit tests for dynamic_suite.Suite.

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
                dependencies=[],
                keyvals={'build': self._BUILD, 'suite': self._TAG}
                ).AndReturn(FakeJob())


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
