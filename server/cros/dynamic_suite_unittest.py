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
from autotest_lib.frontend.afe.json_rpc import proxy
from autotest_lib.server.cros import control_file_getter, dynamic_suite
from autotest_lib.server import frontend

class FakeJob(object):
    """Faked out RPC-client-side Job object."""
    def __init__(self, id=0, statuses=[]):
        self.id = id
        self.hostname = 'host%d' % id
        self.owner = 'tester'
        self.name = 'Fake Job %d' % self.id
        self.statuses = statuses


class FakeHost(object):
    """Faked out RPC-client-side Host object."""
    def __init__(self, status='Ready'):
        self.status = status

class FakeLabel(object):
    """Faked out RPC-client-side Label object."""
    def __init__(self, id=0):
        self.id = id


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
        build, board, name, job, _, _, _, _,_ = \
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
            for k,v in d.iteritems():
                if isinstance(v, str):
                    if "%s='%s'\n" % (k,v) not in s:
                        return False
                else:
                    if "%s=%r\n" % (k,v) not in s:
                        return False
            return True

        v = {'v1': 'one', 'v2': 'two', 'v3': None, 'v4': False, 'v5': 5}
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
            meta_hosts=[self._BOARD] * self._NUM,
            dependencies=[],
            priority='Low')
        self.mox.ReplayAll()
        self.reimager._schedule_reimage_job(self._BUILD, self._NUM, self._BOARD)


    def expect_attempt(self, success, ex=None, check_hosts=True):
        """Sets up |self.reimager| to expect an attempt() that returns |success|

        Also stubs out Reimger._clear_build_state(), should the caller wish
        to set an expectation there as well.

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
        if check_hosts:
            self.mox.StubOutWithMock(self.reimager, '_count_usable_hosts')
            self.reimager._count_usable_hosts(
                mox.IgnoreArg()).AndReturn(self._NUM)

        if success is not None:
            self.mox.StubOutWithMock(self.reimager, '_report_results')
            self.reimager._report_results(canary, mox.IgnoreArg())
            canary.results_platform_map = {None: {'Total': [canary.hostname]}}


        self.afe.get_jobs(id=canary.id, not_yet_run=True).AndReturn([])
        if ex is not None:
            self.afe.get_jobs(id=canary.id, finished=True).AndRaise(ex)
        else:
            self.afe.get_jobs(id=canary.id, finished=True).AndReturn([canary])
            self.afe.poll_job_results(mox.IgnoreArg(),
                                      canary, 0).AndReturn(success)

        self.mox.StubOutWithMock(self.reimager, '_clear_build_state')

        return canary


    def testSuccessfulReimage(self):
        """Should attempt a reimage and record success."""
        canary = self.expect_attempt(success=True)

        rjob = self.mox.CreateMock(base_job.base_job)
        rjob.record('START', mox.IgnoreArg(), mox.IgnoreArg())
        rjob.record('END GOOD', mox.IgnoreArg(), mox.IgnoreArg())
        self.reimager._clear_build_state(mox.StrContains(canary.hostname))
        self.mox.ReplayAll()
        self.reimager.attempt(self._BUILD, self._BOARD, rjob.record, True)
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testFailedReimage(self):
        """Should attempt a reimage and record failure."""
        canary = self.expect_attempt(success=False)

        rjob = self.mox.CreateMock(base_job.base_job)
        rjob.record('START', mox.IgnoreArg(), mox.IgnoreArg())
        rjob.record('END FAIL', mox.IgnoreArg(), mox.IgnoreArg())
        self.reimager._clear_build_state(mox.StrContains(canary.hostname))
        self.mox.ReplayAll()
        self.reimager.attempt(self._BUILD, self._BOARD, rjob.record, True)
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testReimageThatNeverHappened(self):
        """Should attempt a reimage and record that it didn't run."""
        canary = self.expect_attempt(success=None)

        rjob = self.mox.CreateMock(base_job.base_job)
        rjob.record('START', mox.IgnoreArg(), mox.IgnoreArg())
        rjob.record('FAIL', mox.IgnoreArg(), canary.name, mox.IgnoreArg())
        rjob.record('END FAIL', mox.IgnoreArg(), mox.IgnoreArg())
        self.mox.ReplayAll()
        self.reimager.attempt(self._BUILD, self._BOARD, rjob.record, True)
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testReimageThatRaised(self):
        """Should attempt a reimage that raises an exception and record that."""
        ex_message = 'Oh no!'
        canary = self.expect_attempt(success=None, ex=Exception(ex_message))

        rjob = self.mox.CreateMock(base_job.base_job)
        rjob.record('START', mox.IgnoreArg(), mox.IgnoreArg())
        rjob.record('END ERROR', mox.IgnoreArg(), mox.IgnoreArg(), ex_message)
        self.mox.ReplayAll()
        self.reimager.attempt(self._BUILD, self._BOARD, rjob.record, True)
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testSuccessfulReimageThatCouldNotScheduleRightAway(self):
        """Should attempt reimage, ignoring host availability; record success.
        """
        canary = self.expect_attempt(success=True, check_hosts=False)

        rjob = self.mox.CreateMock(base_job.base_job)
        rjob.record('START', mox.IgnoreArg(), mox.IgnoreArg())
        rjob.record('END GOOD', mox.IgnoreArg(), mox.IgnoreArg())
        self.reimager._clear_build_state(mox.StrContains(canary.hostname))
        self.mox.ReplayAll()
        self.reimager.attempt(self._BUILD, self._BOARD, rjob.record, False)
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testReimageThatCouldNotSchedule(self):
        """Should attempt a reimage that can't be scheduled."""
        self.mox.StubOutWithMock(self.reimager, '_ensure_version_label')
        self.reimager._ensure_version_label(mox.StrContains(self._BUILD))

        self.mox.StubOutWithMock(self.reimager, '_count_usable_hosts')
        self.reimager._count_usable_hosts(mox.IgnoreArg()).AndReturn(1)

        rjob = self.mox.CreateMock(base_job.base_job)
        rjob.record('START', mox.IgnoreArg(), mox.IgnoreArg())
        rjob.record('END WARN', mox.IgnoreArg(), mox.IgnoreArg(),
                    mox.StrContains('Too few hosts'))
        self.mox.ReplayAll()
        self.reimager.attempt(self._BUILD, self._BOARD, rjob.record, True)
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testReimageWithNoAvailableHosts(self):
        """Should attempt a reimage while all hosts are dead."""
        self.mox.StubOutWithMock(self.reimager, '_ensure_version_label')
        self.reimager._ensure_version_label(mox.StrContains(self._BUILD))

        self.mox.StubOutWithMock(self.reimager, '_count_usable_hosts')
        self.reimager._count_usable_hosts(mox.IgnoreArg()).AndReturn(0)

        rjob = self.mox.CreateMock(base_job.base_job)
        rjob.record('START', mox.IgnoreArg(), mox.IgnoreArg())
        rjob.record('END ERROR', mox.IgnoreArg(), mox.IgnoreArg(),
                    mox.StrContains('All hosts'))
        self.mox.ReplayAll()
        self.reimager.attempt(self._BUILD, self._BOARD, rjob.record, True)
        self.reimager.clear_reimaged_host_state(self._BUILD)


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


class SuiteTest(mox.MoxTestBase):
    """Unit tests for dynamic_suite.Suite.

    @var _BUILD: fake build
    @var _TAG: fake suite tag
    """

    _BUILD = 'build'
    _TAG = 'suite_tag'


    class FakeControlData(object):
        """A fake parsed control file data structure."""
        def __init__(self, data, expr=False):
            self.string = 'text-' + data
            self.name = 'name-' + data
            self.data = data
            self.suite = SuiteTest._TAG
            self.test_type = 'Client'
            self.experimental = expr


    def setUp(self):
        super(SuiteTest, self).setUp()
        self.afe = self.mox.CreateMock(frontend.AFE)
        self.tko = self.mox.CreateMock(frontend.TKO)

        self.tmpdir = tempfile.mkdtemp(suffix=type(self).__name__)

        self.getter = self.mox.CreateMock(control_file_getter.ControlFileGetter)

        self.files = {'one': SuiteTest.FakeControlData('data_one', expr=True),
                      'two': SuiteTest.FakeControlData('data_two'),
                      'three': SuiteTest.FakeControlData('data_three')}

        self.files_to_filter = {
            'with/deps/...': SuiteTest.FakeControlData('...gets filtered'),
            'with/profilers/...': SuiteTest.FakeControlData('...gets filtered')}


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
                self.test_started_time = '2012-11-11 11:11:11'
                self.test_finished_time = '2012-11-11 12:12:12'
                if aborted:
                    self.entry['aborted'] = True

            def equals_record(self, status):
                """Compares this object to a recorded status."""
                return self._equals_record(status._status, status._test_name,
                                           status._reason)

            def _equals_record(self, status, name, reason=None):
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


    def schedule_and_expect_these_results(self, suite, results, recorder):
        self.mox.StubOutWithMock(suite, 'schedule')
        suite.schedule(True)
        for result in results:
            status = result[0]
            test_name = result[1]
            recorder.record_entry(
                StatusContains.CreateFromStrings('START', test_name))
            recorder.record_entry(
                StatusContains.CreateFromStrings(*result)).InAnyOrder('results')
            recorder.record_entry(
                StatusContains.CreateFromStrings('END %s' % status, test_name))
        self.mox.StubOutWithMock(suite, 'wait_for_results')
        suite.wait_for_results().AndReturn(
            map(lambda r: dynamic_suite.Status(*r), results))


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

        suite.run_and_wait(recorder.record_entry, True)


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
        self.mox.StubOutWithMock(suite, 'wait_for_results')
        suite.wait_for_results().AndRaise(Exception('Expected during test.'))
        self.expect_control_file_reparsing()
        self.mox.ReplayAll()

        suite.run_and_wait(recorder.record_entry, True)


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

        suite.run_and_wait(recorder.record_entry, True)


    def testRunAndWaitDevServerRacyFailure(self):
        """Should record discovery of dev server races in listing files."""
        suite = self._createSuiteWithMockedTestsAndControlFiles()

        recorder = self.mox.CreateMock(base_job.base_job)
        recorder.record_entry(
            StatusContains.CreateFromStrings('INFO', 'Start %s' % self._TAG))

        results = [('GOOD', 'good'), ('FAIL', 'bad', 'reason')]
        self.schedule_and_expect_these_results(suite, results, recorder)

        self.expect_racy_control_file_reparsing(
            {'new': SuiteTest.FakeControlData('!')})

        recorder.record_entry(
            StatusContains.CreateFromStrings('FAIL', self._TAG, 'Dev Server'))
        self.mox.ReplayAll()

        suite.run_and_wait(recorder.record_entry, True)


if __name__ == '__main__':
  unittest.main()
