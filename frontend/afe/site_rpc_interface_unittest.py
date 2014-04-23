#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for frontend/afe/site_rpc_interface.py."""


import mox
import unittest

import common

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import priorities
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.frontend.afe import site_rpc_interface
from autotest_lib.server.cros.dynamic_suite import control_file_getter
from autotest_lib.server.cros.dynamic_suite import constants


class SiteRpcInterfaceTest(mox.MoxTestBase):
    """Unit tests for functions in site_rpc_interface.py.

    @var _NAME: fake suite name.
    @var _BOARD: fake board to reimage.
    @var _BUILD: fake build with which to reimage.
    @var _PRIORITY: fake priority with which to reimage.
    """
    _NAME = 'name'
    _BOARD = 'link'
    _BUILD = 'link-release/R36-5812.0.0'
    _PRIORITY = priorities.Priority.DEFAULT
    _TIMEOUT = 24


    class rpc_utils(object):
        """Mockable class to fake autotest rpc_utils module."""
        def create_job_common(self, name, **kwargs):
            """Mock method rpc_utils.create_job_common().

            @param name: Name of job.
            @param kwargs: Other arguments.
            """
            pass


    def setUp(self):
        super(SiteRpcInterfaceTest, self).setUp()
        self._SUITE_NAME = site_rpc_interface.canonicalize_suite_name(
            self._NAME)
        self.dev_server = self.mox.CreateMock(dev_server.ImageServer)


    def _setupDevserver(self):
        self.mox.StubOutClassWithMocks(dev_server, 'ImageServer')
        dev_server.ImageServer.resolve(self._BUILD).AndReturn(self.dev_server)


    def _mockDevServerGetter(self, get_control_file=True):
        self._setupDevserver()
        if get_control_file:
          self.getter = self.mox.CreateMock(
              control_file_getter.DevServerGetter)
          self.mox.StubOutWithMock(control_file_getter.DevServerGetter,
                                   'create')
          control_file_getter.DevServerGetter.create(
              mox.IgnoreArg(), mox.IgnoreArg()).AndReturn(self.getter)


    def _mockRpcUtils(self, to_return, control_file_substring=''):
        """Fake out the autotest rpc_utils module with a mockable class.

        @param to_return: the value that rpc_utils.create_job_common() should
                          be mocked out to return.
        @param control_file_substring: A substring that is expected to appear
                                       in the control file output string that
                                       is passed to create_job_common.
                                       Default: ''
        """
        download_started_time = constants.DOWNLOAD_STARTED_TIME
        payload_finished_time = constants.PAYLOAD_FINISHED_TIME
        r = self.mox.CreateMock(SiteRpcInterfaceTest.rpc_utils)
        r.create_job_common(mox.And(mox.StrContains(self._NAME),
                                    mox.StrContains(self._BUILD)),
                            priority=self._PRIORITY,
                            timeout_mins=self._TIMEOUT*60,
                            max_runtime_mins=self._TIMEOUT*60,
                            control_type='Server',
                            control_file=mox.And(mox.StrContains(self._BOARD),
                                                 mox.StrContains(self._BUILD),
                                                 mox.StrContains(
                                                     control_file_substring)),
                            hostless=True,
                            keyvals=mox.And(mox.In(download_started_time),
                                            mox.In(payload_finished_time))
                            ).AndReturn(to_return)
        self.mox.StubOutWithMock(site_rpc_interface, '_rpc_utils')
        site_rpc_interface._rpc_utils().AndReturn(r)


    def testStageBuildFail(self):
        """Ensure that a failure to stage the desired build fails the RPC."""
        self._setupDevserver()
        self.dev_server.stage_artifacts(
            self._BUILD, ['test_suites']).AndRaise(
                dev_server.DevServerException())
        self.mox.ReplayAll()
        self.assertRaises(error.StageBuildFailure,
                          site_rpc_interface.create_suite_job,
                          self._NAME,
                          self._BOARD,
                          self._BUILD,
                          None)


    def testGetControlFileFail(self):
        """Ensure that a failure to get needed control file fails the RPC."""
        self._mockDevServerGetter()
        self.dev_server.stage_artifacts(self._BUILD,
                                        ['test_suites']).AndReturn(True)
        self.getter.get_control_file_contents_by_name(
            self._SUITE_NAME).AndReturn(None)
        self.mox.ReplayAll()
        self.assertRaises(error.ControlFileEmpty,
                          site_rpc_interface.create_suite_job,
                          self._NAME,
                          self._BOARD,
                          self._BUILD,
                          None)


    def testGetControlFileListFail(self):
        """Ensure that a failure to get needed control file fails the RPC."""
        self._mockDevServerGetter()
        self.dev_server.stage_artifacts(self._BUILD,
                                        ['test_suites']).AndReturn(True)
        self.getter.get_control_file_contents_by_name(
            self._SUITE_NAME).AndRaise(error.NoControlFileList())
        self.mox.ReplayAll()
        self.assertRaises(error.NoControlFileList,
                          site_rpc_interface.create_suite_job,
                          self._NAME,
                          self._BOARD,
                          self._BUILD,
                          None)


    def testBadNumArgument(self):
        """Ensure we handle bad values for the |num| argument."""
        self.assertRaises(error.SuiteArgumentException,
                          site_rpc_interface.create_suite_job,
                          self._NAME,
                          self._BOARD,
                          self._BUILD,
                          None,
                          num='goo')
        self.assertRaises(error.SuiteArgumentException,
                          site_rpc_interface.create_suite_job,
                          self._NAME,
                          self._BOARD,
                          self._BUILD,
                          None,
                          num=[])
        self.assertRaises(error.SuiteArgumentException,
                          site_rpc_interface.create_suite_job,
                          self._NAME,
                          self._BOARD,
                          self._BUILD,
                          None,
                          num='5')



    def testCreateSuiteJobFail(self):
        """Ensure that failure to schedule the suite job fails the RPC."""
        self._mockDevServerGetter()
        self.dev_server.stage_artifacts(self._BUILD,
                                        ['test_suites']).AndReturn(True)
        self.dev_server.url().AndReturn('mox_url')
        self.getter.get_control_file_contents_by_name(
            self._SUITE_NAME).AndReturn('f')
        self._mockRpcUtils(-1)
        self.mox.ReplayAll()
        self.assertEquals(
            site_rpc_interface.create_suite_job(name=self._NAME,
                                                board=self._BOARD,
                                                build=self._BUILD, pool=None),
            -1)


    def testCreateSuiteJobSuccess(self):
        """Ensures that success results in a successful RPC."""
        self._mockDevServerGetter()
        self.dev_server.stage_artifacts(self._BUILD,
                                        ['test_suites']).AndReturn(True)
        self.dev_server.url().AndReturn('mox_url')
        self.getter.get_control_file_contents_by_name(
            self._SUITE_NAME).AndReturn('f')
        job_id = 5
        self._mockRpcUtils(job_id)
        self.mox.ReplayAll()
        self.assertEquals(
            site_rpc_interface.create_suite_job(name=self._NAME,
                                                board=self._BOARD,
                                                build=self._BUILD,
                                                pool=None),
            job_id)


    def testCreateSuiteJobNoHostCheckSuccess(self):
        """Ensures that success results in a successful RPC."""
        self._mockDevServerGetter()
        self.dev_server.stage_artifacts(self._BUILD,
                                        ['test_suites']).AndReturn(True)
        self.dev_server.url().AndReturn('mox_url')
        self.getter.get_control_file_contents_by_name(
            self._SUITE_NAME).AndReturn('f')
        job_id = 5
        self._mockRpcUtils(job_id)
        self.mox.ReplayAll()
        self.assertEquals(
          site_rpc_interface.create_suite_job(name=self._NAME,
                                              board=self._BOARD,
                                              build=self._BUILD,
                                              pool=None, check_hosts=False),
          job_id)

    def testCreateSuiteIntegerNum(self):
        """Ensures that success results in a successful RPC."""
        self._mockDevServerGetter()
        self.dev_server.stage_artifacts(self._BUILD,
                                        ['test_suites']).AndReturn(True)
        self.dev_server.url().AndReturn('mox_url')
        self.getter.get_control_file_contents_by_name(
            self._SUITE_NAME).AndReturn('f')
        job_id = 5
        self._mockRpcUtils(job_id, control_file_substring='num=17')
        self.mox.ReplayAll()
        self.assertEquals(
            site_rpc_interface.create_suite_job(name=self._NAME,
                                                board=self._BOARD,
                                                build=self._BUILD,
                                                pool=None,
                                                check_hosts=False,
                                                num=17),
            job_id)


    def testCreateSuiteJobControlFileSupplied(self):
        """Ensure we can supply the control file to create_suite_job."""
        self._mockDevServerGetter(get_control_file=False)
        self.dev_server.stage_artifacts(self._BUILD,
                                        ['test_suites']).AndReturn(True)
        self.dev_server.url().AndReturn('mox_url')
        job_id = 5
        self._mockRpcUtils(job_id)
        self.mox.ReplayAll()
        self.assertEquals(
            site_rpc_interface.create_suite_job(name='%s/%s' % (self._NAME,
                                                                self._BUILD),
                                                board=None,
                                                build=self._BUILD,
                                                pool=None,
                                                control_file='CONTROL FILE'),
            job_id)



if __name__ == '__main__':
  unittest.main()
