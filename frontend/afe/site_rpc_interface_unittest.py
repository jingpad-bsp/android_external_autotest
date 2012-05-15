#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for frontend/afe/site_rpc_interface.py."""

import common
import mox
import unittest
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.frontend.afe import site_rpc_interface
from autotest_lib.server.cros import control_file_getter, dynamic_suite


class SiteRpcInterfaceTest(mox.MoxTestBase):
    """Unit tests for functions in site_rpc_interface.py.

    @var _NAME: fake suite name.
    @var _BOARD: fake board to reimage.
    @var _BUILD: fake build with which to reimage.
    """
    _NAME = 'name'
    _BOARD = 'board'
    _BUILD = 'build'


    class rpc_utils(object):
        def create_job_common(self, name, **kwargs):
            pass


    def setUp(self):
        super(SiteRpcInterfaceTest, self).setUp()
        self._SUITE_NAME = site_rpc_interface.canonicalize_suite_name(
            self._NAME)
        self.dev_server = self.mox.CreateMock(dev_server.DevServer)
        self.mox.StubOutWithMock(dev_server.DevServer, 'create')
        dev_server.DevServer.create().AndReturn(self.dev_server)


    def _mockDevServerGetter(self):
        self.getter = self.mox.CreateMock(control_file_getter.DevServerGetter)
        self.mox.StubOutWithMock(control_file_getter.DevServerGetter, 'create')
        control_file_getter.DevServerGetter.create(
            mox.IgnoreArg(), mox.IgnoreArg()).AndReturn(self.getter)


    def _mockRpcUtils(self, to_return):
        """Fake out the autotest rpc_utils module with a mockable class.

        @param to_return: the value that rpc_utils.create_job_common() should
                          be mocked out to return.
        """
        download_started_time = dynamic_suite.DOWNLOAD_STARTED_TIME
        payload_finished_time = dynamic_suite.PAYLOAD_FINISHED_TIME
        r = self.mox.CreateMock(SiteRpcInterfaceTest.rpc_utils)
        r.create_job_common(mox.And(mox.StrContains(self._NAME),
                                    mox.StrContains(self._BUILD)),
                            priority='Medium',
                            control_type='Server',
                            control_file=mox.And(mox.StrContains(self._BOARD),
                                                 mox.StrContains(self._BUILD)),
                            hostless=True,
                            keyvals=mox.And(mox.In(download_started_time),
                                            mox.In(payload_finished_time))
                            ).AndReturn(to_return)
        self.mox.StubOutWithMock(site_rpc_interface, '_rpc_utils')
        site_rpc_interface._rpc_utils().AndReturn(r)


    def testStageBuildFail(self):
        """Ensure that a failure to stage the desired build fails the RPC."""
        self.dev_server.trigger_download(
            self._BUILD, synchronous=False).AndRaise(
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
        self.dev_server.trigger_download(self._BUILD,
                                         synchronous=False).AndReturn(True)
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
        self.dev_server.trigger_download(self._BUILD,
                                         synchronous=False).AndReturn(True)
        self.getter.get_control_file_contents_by_name(
            self._SUITE_NAME).AndRaise(error.NoControlFileList())
        self.mox.ReplayAll()
        self.assertRaises(error.NoControlFileList,
                          site_rpc_interface.create_suite_job,
                          self._NAME,
                          self._BOARD,
                          self._BUILD,
                          None)


    def testCreateSuiteJobFail(self):
        """Ensure that failure to schedule the suite job fails the RPC."""
        self._mockDevServerGetter()
        self.dev_server.trigger_download(self._BUILD,
                                         synchronous=False).AndReturn(True)
        self.getter.get_control_file_contents_by_name(
            self._SUITE_NAME).AndReturn('f')
        self._mockRpcUtils(-1)
        self.mox.ReplayAll()
        self.assertEquals(site_rpc_interface.create_suite_job(self._NAME,
                                                              self._BOARD,
                                                              self._BUILD,
                                                              None),
                          - 1)


    def testCreateSuiteJobSuccess(self):
        """Ensures that success results in a successful RPC."""
        self._mockDevServerGetter()
        self.dev_server.trigger_download(self._BUILD,
                                         synchronous=False).AndReturn(True)
        self.getter.get_control_file_contents_by_name(
            self._SUITE_NAME).AndReturn('f')
        job_id = 5
        self._mockRpcUtils(job_id)
        self.mox.ReplayAll()
        self.assertEquals(site_rpc_interface.create_suite_job(self._NAME,
                                                              self._BOARD,
                                                              self._BUILD,
                                                              None),
                          job_id)


    def testCreateSuiteJobNoHostCheckSuccess(self):
        """Ensures that success results in a successful RPC."""
        self._mockDevServerGetter()
        self.dev_server.trigger_download(self._BUILD,
                                         synchronous=False).AndReturn(True)
        self.getter.get_control_file_contents_by_name(
            self._SUITE_NAME).AndReturn('f')
        job_id = 5
        self._mockRpcUtils(job_id)
        self.mox.ReplayAll()
        self.assertEquals(site_rpc_interface.create_suite_job(self._NAME,
                                                              self._BOARD,
                                                              self._BUILD,
                                                              None,
                                                              False),
                          job_id)


if __name__ == '__main__':
  unittest.main()
