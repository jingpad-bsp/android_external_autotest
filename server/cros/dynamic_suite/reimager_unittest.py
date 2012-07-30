#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for server/cros/dynamic_suite/reimager.py."""

import logging
import mox
import unittest

from autotest_lib.client.common_lib import base_job, control_data, error
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.frontend.afe.json_rpc import proxy
from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.server.cros.dynamic_suite import control_file_getter
from autotest_lib.server.cros.dynamic_suite import host_lock_manager, job_status
from autotest_lib.server.cros.dynamic_suite import tools
from autotest_lib.server.cros.dynamic_suite.comparitors import StatusContains
from autotest_lib.server.cros.dynamic_suite.reimager import Reimager
from autotest_lib.server.cros.dynamic_suite.fakes import FakeHost, FakeJob
from autotest_lib.server import frontend


class ReimagerTest(mox.MoxTestBase):
    """Unit tests for dynamic_suite Reimager class.

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
        self.reimager = Reimager('', afe=self.afe, tko=self.tko)
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


    def testIncorrectlyLocked(self):
        """Should detect hosts locked by random users."""
        host = FakeHost(locked=True)
        host.locked_by = 'some guy'
        self.assertTrue(self.reimager._incorrectly_locked(host))


    def testNotIncorrectlyLocked(self):
        """Should accept hosts locked by the infrastructure."""
        infra_user = 'an infra user'
        self.mox.StubOutWithMock(tools, 'infrastructure_user_list')
        tools.infrastructure_user_list().AndReturn([infra_user])
        host = FakeHost(locked=True, locked_by=infra_user)
        self.mox.ReplayAll()
        self.assertFalse(self.reimager._incorrectly_locked(host))


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


    def testCountAllHostsIncorrectlyLockedByBoard(self):
        """Should count the available hosts, by board, getting a locked host."""
        spec = [self._BOARD]
        badly_locked_host = FakeHost(locked=True, locked_by = 'some guy')
        self.afe.get_hosts(multiple_labels=spec).AndReturn([badly_locked_host])
        self.mox.ReplayAll()
        self.assertEquals(self.reimager._count_usable_hosts(spec), 0)


    def testCountAllHostsInfraLockedByBoard(self):
        """Should count the available hosts, get a host locked by infra."""
        infra_user = 'an infra user'
        self.mox.StubOutWithMock(tools, 'infrastructure_user_list')
        spec = [self._BOARD]
        self.afe.get_hosts(multiple_labels=spec).AndReturn(
            [FakeHost(locked=True, locked_by=infra_user)])
        tools.infrastructure_user_list().AndReturn([infra_user])
        self.mox.ReplayAll()
        self.assertEquals(self.reimager._count_usable_hosts(spec), 1)


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
        package_url = tools.get_package_url(self._BUILD)
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
                    mox.StrContains(Reimager.JOB_NAME)).AndReturn(
                            statuses)

        if statuses:
            ret_val = reduce(lambda v, s: v or s.is_good(),
                             statuses.values(), False)
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


    def testPartialReimage(self):
        """Should attempt a reimage with failing hosts and record success."""
        canary = FakeJob(hostnames=['host1', 'host2'])
        statuses = {
            canary.hostnames[0]: job_status.Status('FAIL', canary.hostnames[0]),
            canary.hostnames[1]: job_status.Status('GOOD', canary.hostnames[1]),
        }
        self.expect_attempt(canary, statuses)

        rjob = self.mox.CreateMock(base_job.base_job)
        comparator = mox.Or(mox.StrContains('host1'), mox.StrContains('host2'))
        self.reimager._clear_build_state(comparator)
        self.reimager._clear_build_state(comparator)
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
