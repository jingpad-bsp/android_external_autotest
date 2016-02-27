#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for client/common_lib/cros/dev_server.py."""

import httplib
import mox
import StringIO
import time
import unittest
import urllib2

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib import utils
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.client.common_lib.cros import retry

def retry_mock(ExceptionToCheck, timeout_min):
    """A mock retry decorator to use in place of the actual one for testing.

    @param ExceptionToCheck: the exception to check.
    @param timeout_mins: Amount of time in mins to wait before timing out.

    """
    def inner_retry(func):
        """The actual decorator.

        @param func: Function to be called in decorator.

        """
        return func

    return inner_retry


class MockSshResponse(object):
    """An ssh response mocked for testing."""

    def __init__(self, output, exit_status=0):
        self.stdout = output
        self.exit_status = exit_status
        self.stderr = 'SSH connection error occurred.'


class MockSshError(error.CmdError):
    """An ssh error response mocked for testing."""

    def __init__(self, exit_status):
        self.result_obj = MockSshResponse('error', exit_status=255)


class DevServerTest(mox.MoxTestBase):
    """Unit tests for dev_server.DevServer.

    @var _HOST: fake dev server host address.
    """

    _HOST = 'http://nothing'
    _CRASH_HOST = 'http://nothing-crashed'
    _CONFIG = global_config.global_config


    def setUp(self):
        super(DevServerTest, self).setUp()
        self.crash_server = dev_server.CrashServer(DevServerTest._CRASH_HOST)
        self.dev_server = dev_server.ImageServer(DevServerTest._HOST)
        self.android_dev_server = dev_server.AndroidBuildServer(
                DevServerTest._HOST)
        self.mox.StubOutWithMock(urllib2, 'urlopen')
        self.mox.StubOutWithMock(utils, 'run')
        # Hide local restricted_subnets setting.
        dev_server.RESTRICTED_SUBNETS = []


    def testSimpleResolve(self):
        """One devserver, verify we resolve to it."""
        self.mox.StubOutWithMock(dev_server, '_get_dev_server_list')
        self.mox.StubOutWithMock(dev_server.ImageServer, 'devserver_healthy')
        dev_server._get_dev_server_list().MultipleTimes().AndReturn(
                [DevServerTest._HOST])
        dev_server.ImageServer.devserver_healthy(DevServerTest._HOST).AndReturn(
                                                                        True)
        self.mox.ReplayAll()
        devserver = dev_server.ImageServer.resolve('my_build')
        self.assertEquals(devserver.url(), DevServerTest._HOST)


    def testResolveWithFailureHTTP(self):
        """Ensure we rehash on a failed ping on a bad_host use HTTP call."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False
        self.mox.StubOutWithMock(dev_server, '_get_dev_server_list')
        bad_host, good_host = 'http://bad_host:99', 'http://good_host:8080'
        dev_server._get_dev_server_list().MultipleTimes().AndReturn(
                [bad_host, good_host])
        argument1 = mox.StrContains(bad_host)
        argument2 = mox.StrContains(good_host)

        # Mock out bad ping failure to bad_host by raising devserver exception.
        urllib2.urlopen(argument1, data=None).AndRaise(
                dev_server.DevServerException())
        # Good host is good.
        to_return = StringIO.StringIO('{"free_disk": 1024}')
        urllib2.urlopen(argument2, data=None).AndReturn(to_return)

        self.mox.ReplayAll()
        host = dev_server.ImageServer.resolve(0) # Using 0 as it'll hash to 0.
        self.assertEquals(host.url(), good_host)
        self.mox.VerifyAll()

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testResolveWithFailureSSH(self):
        """Ensure we rehash on a failed ping on a bad_host use SSH call."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = True

        self.mox.StubOutWithMock(dev_server, '_get_dev_server_list')
        bad_host, good_host = 'http://bad_host:99', 'http://good_host:8080'
        dev_server._get_dev_server_list().MultipleTimes().AndReturn(
                [bad_host, good_host])
        argument1 = mox.StrContains(bad_host)
        argument2 = mox.StrContains(good_host)

        # Mock out bad ping failure to bad_host by raising devserver exception.
        utils.run(argument1, timeout=mox.IgnoreArg()).AndRaise(
                dev_server.DevServerException())
        # Good host is good.
        to_return = MockSshResponse('{"free_disk": 1024}')
        utils.run(argument2, timeout=mox.IgnoreArg()).AndReturn(to_return)

        self.mox.ReplayAll()
        host = dev_server.ImageServer.resolve(0) # Using 0 as it'll hash to 0.
        self.assertEquals(host.url(), good_host)
        self.mox.VerifyAll()

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testResolveWithFailureURLError(self):
        """Ensure we rehash on a failed ping using http on a bad_host after
        urlerror."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        # Retry mock just return the original method.
        retry.retry = retry_mock
        self.mox.StubOutWithMock(dev_server, '_get_dev_server_list')
        bad_host, good_host = 'http://bad_host:99', 'http://good_host:8080'
        dev_server._get_dev_server_list().MultipleTimes().AndReturn(
                [bad_host, good_host])
        argument1 = mox.StrContains(bad_host)
        argument2 = mox.StrContains(good_host)

        # Mock out bad ping failure to bad_host by raising devserver exception.
        urllib2.urlopen(argument1, data=None).MultipleTimes().AndRaise(
                urllib2.URLError('urlopen connection timeout'))

        # Good host is good.
        to_return = StringIO.StringIO('{"free_disk": 1024}')
        urllib2.urlopen(argument2, data=None).AndReturn(to_return)

        self.mox.ReplayAll()
        host = dev_server.ImageServer.resolve(0) # Using 0 as it'll hash to 0.
        self.assertEquals(host.url(), good_host)
        self.mox.VerifyAll()

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testResolveWithManyDevservers(self):
        """Should be able to return different urls with multiple devservers."""
        self.mox.StubOutWithMock(dev_server.ImageServer, 'servers')
        self.mox.StubOutWithMock(dev_server.DevServer, 'devserver_healthy')

        host0_expected = 'http://host0:8080'
        host1_expected = 'http://host1:8082'

        dev_server.ImageServer.servers().MultipleTimes().AndReturn(
                [host0_expected, host1_expected])
        dev_server.ImageServer.devserver_healthy(host0_expected).AndReturn(True)
        dev_server.ImageServer.devserver_healthy(host1_expected).AndReturn(True)

        self.mox.ReplayAll()
        host0 = dev_server.ImageServer.resolve(0)
        host1 = dev_server.ImageServer.resolve(1)
        self.mox.VerifyAll()

        self.assertEqual(host0.url(), host0_expected)
        self.assertEqual(host1.url(), host1_expected)


    def _returnHttpServerError(self):
        e500 = urllib2.HTTPError(url='',
                                 code=httplib.INTERNAL_SERVER_ERROR,
                                 msg='',
                                 hdrs=None,
                                 fp=StringIO.StringIO('Expected.'))
        urllib2.urlopen(mox.IgnoreArg()).AndRaise(e500)


    def _returnHttpForbidden(self):
        e403 = urllib2.HTTPError(url='',
                                 code=httplib.FORBIDDEN,
                                 msg='',
                                 hdrs=None,
                                 fp=StringIO.StringIO('Expected.'))
        urllib2.urlopen(mox.IgnoreArg()).AndRaise(e403)


    def _returnCmdError(self):
        cmd_error = MockSshError(255)
        utils.run(mox.IgnoreArg(), timeout=mox.IgnoreArg()).AndRaise(cmd_error)


    def testSuccessfulTriggerDownloadSyncHTTP(self):
        """Call the dev server's download method using http with
        synchronous=True."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        name = 'fake/image'
        self.mox.StubOutWithMock(dev_server.ImageServer, '_finish_download')
        argument1 = mox.And(mox.StrContains(self._HOST),
                            mox.StrContains(name),
                            mox.StrContains('stage?'))
        argument2 = mox.And(mox.StrContains(self._HOST),
                            mox.StrContains(name),
                            mox.StrContains('is_staged'))
        to_return = StringIO.StringIO('Success')
        urllib2.urlopen(argument1).AndReturn(to_return)
        to_return = StringIO.StringIO('True')
        urllib2.urlopen(argument2).AndReturn(to_return)
        self.dev_server._finish_download(name, mox.IgnoreArg(), mox.IgnoreArg())

        # Synchronous case requires a call to finish download.
        self.mox.ReplayAll()
        self.dev_server.trigger_download(name, synchronous=True)
        self.mox.VerifyAll()

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testSuccessfulTriggerDownloadSyncSSH(self):
        """Call the dev server's download method using ssh with
        synchronous=True."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = True
        name = 'fake/image'
        self.mox.StubOutWithMock(dev_server.ImageServer, '_finish_download')
        argument1 = mox.And(mox.StrContains(self._HOST),
                            mox.StrContains(name),
                            mox.StrContains('stage?'))
        argument2 = mox.And(mox.StrContains(self._HOST),
                            mox.StrContains(name),
                            mox.StrContains('is_staged'))
        to_return = MockSshResponse('Success')
        utils.run(argument1, timeout=mox.IgnoreArg()).AndReturn(to_return)
        to_return = MockSshResponse('True')
        utils.run(argument2, timeout=mox.IgnoreArg()).AndReturn(to_return)
        self.dev_server._finish_download(name, mox.IgnoreArg(), mox.IgnoreArg())

        # Synchronous case requires a call to finish download.
        self.mox.ReplayAll()
        self.dev_server.trigger_download(name, synchronous=True)
        self.mox.VerifyAll()

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testSuccessfulTriggerDownloadASyncHTTP(self):
        """Call the dev server's download method using http with
        synchronous=False."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        name = 'fake/image'
        argument1 = mox.And(mox.StrContains(self._HOST), mox.StrContains(name),
                            mox.StrContains('stage?'))
        argument2 = mox.And(mox.StrContains(self._HOST), mox.StrContains(name),
                            mox.StrContains('is_staged'))
        to_return = StringIO.StringIO('Success')
        urllib2.urlopen(argument1).AndReturn(to_return)
        to_return = StringIO.StringIO('True')
        urllib2.urlopen(argument2).AndReturn(to_return)

        self.mox.ReplayAll()
        self.dev_server.trigger_download(name, synchronous=False)
        self.mox.VerifyAll()

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testSuccessfulTriggerDownloadASyncSSH(self):
        """Call the dev server's download method using ssh with
        synchronous=False."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = True

        name = 'fake/image'
        argument1 = mox.And(mox.StrContains(self._HOST), mox.StrContains(name),
                            mox.StrContains('stage?'))
        argument2 = mox.And(mox.StrContains(self._HOST), mox.StrContains(name),
                            mox.StrContains('is_staged'))
        to_return = MockSshResponse('Success')
        utils.run(argument1, timeout=mox.IgnoreArg()).AndReturn(to_return)
        to_return = MockSshResponse('True')
        utils.run(argument2, timeout=mox.IgnoreArg()).AndReturn(to_return)

        self.mox.ReplayAll()
        self.dev_server.trigger_download(name, synchronous=False)
        self.mox.VerifyAll()

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testURLErrorRetryTriggerDownload(self):
        """Should retry on URLError, but pass through real exception."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        self.mox.StubOutWithMock(time, 'sleep')

        refused = urllib2.URLError('[Errno 111] Connection refused')
        urllib2.urlopen(mox.IgnoreArg()).AndRaise(refused)
        time.sleep(mox.IgnoreArg())
        self._returnHttpForbidden()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.trigger_download,
                          '')

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testErrorTriggerDownload(self):
        """Should call the dev server's download method using http, fail
        gracefully."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        self._returnHttpServerError()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.trigger_download,
                          '')

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testForbiddenTriggerDownload(self):
        """Should call the dev server's download method using http,
        get exception."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        self._returnHttpForbidden()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.trigger_download,
                          '')

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testCmdErrorTriggerDownload(self):
        """Should call the dev server's download method using ssh, get
        exception."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = True

        self._returnCmdError()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.trigger_download,
                          '')

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testSuccessfulFinishDownloadHTTP(self):
        """Should successfully call the dev server's finish download method
        using http."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        name = 'fake/image'
        argument1 = mox.And(mox.StrContains(self._HOST),
                            mox.StrContains(name),
                            mox.StrContains('stage?'))
        argument2 = mox.And(mox.StrContains(self._HOST),
                            mox.StrContains(name),
                            mox.StrContains('is_staged'))
        to_return = StringIO.StringIO('Success')
        urllib2.urlopen(argument1).AndReturn(to_return)
        to_return = StringIO.StringIO('True')
        urllib2.urlopen(argument2).AndReturn(to_return)

        # Synchronous case requires a call to finish download.
        self.mox.ReplayAll()
        self.dev_server.finish_download(name)  # Raises on failure.
        self.mox.VerifyAll()

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testSuccessfulFinishDownloadSSH(self):
        """Should successfully call the dev server's finish download method
        using ssh."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = True

        name = 'fake/image'
        argument1 = mox.And(mox.StrContains(self._HOST),
                            mox.StrContains(name),
                            mox.StrContains('stage?'))
        argument2 = mox.And(mox.StrContains(self._HOST),
                            mox.StrContains(name),
                            mox.StrContains('is_staged'))
        to_return = MockSshResponse('Success')
        utils.run(argument1, timeout=mox.IgnoreArg()).AndReturn(to_return)
        to_return = MockSshResponse('True')
        utils.run(argument2, timeout=mox.IgnoreArg()).AndReturn(to_return)

        # Synchronous case requires a call to finish download.
        self.mox.ReplayAll()
        self.dev_server.finish_download(name)  # Raises on failure.
        self.mox.VerifyAll()

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testErrorFinishDownload(self):
        """Should call the dev server's finish download method using http, fail
        gracefully."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        self._returnHttpServerError()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.finish_download,
                          '')

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testCmdErrorFinishDownload(self):
        """Should call the dev server's finish download method using ssh, fail
        gracefully."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = True

        self._returnCmdError()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.finish_download,
                          '')

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testListControlFilesHTTP(self):
        """Should successfully list control files using http from the dev
        server."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        name = 'fake/build'
        control_files = ['file/one', 'file/two']
        argument = mox.And(mox.StrContains(self._HOST),
                           mox.StrContains(name))
        to_return = StringIO.StringIO('\n'.join(control_files))
        urllib2.urlopen(argument).AndReturn(to_return)

        self.mox.ReplayAll()
        paths = self.dev_server.list_control_files(name)
        self.assertEquals(len(paths), 2)
        for f in control_files:
            self.assertTrue(f in paths)

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testListControlFilesSSH(self):
        """Should successfully list control files using ssh from the dev
        server."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = True

        name = 'fake/build'
        control_files = ['file/one', 'file/two']
        argument = mox.And(mox.StrContains(self._HOST),
                           mox.StrContains(name))
        to_return = MockSshResponse('\n'.join(control_files))
        utils.run(argument, timeout=mox.IgnoreArg()).AndReturn(to_return)

        self.mox.ReplayAll()
        paths = self.dev_server.list_control_files(name)
        self.assertEquals(len(paths), 2)
        for f in control_files:
            self.assertTrue(f in paths)

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testFailedListControlFiles(self):
        """Should call the dev server's list-files method using http, get
        exception."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        self._returnHttpServerError()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.list_control_files,
                          '')

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testExplodingListControlFiles(self):
        """Should call the dev server's list-files method using http, get
        exception."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        self._returnHttpForbidden()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.list_control_files,
                          '')

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testCmdErrorListControlFiles(self):
        """Should call the dev server's list-files method using ssh, get
        exception."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = True

        self._returnCmdError()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.list_control_files,
                          '')

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testGetControlFileHTTP(self):
        """Should successfully get a control file from the dev server using
        http."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        name = 'fake/build'
        file = 'file/one'
        contents = 'Multi-line\nControl File Contents\n'
        argument = mox.And(mox.StrContains(self._HOST),
                            mox.StrContains(name),
                            mox.StrContains(file))
        to_return = StringIO.StringIO(contents)
        urllib2.urlopen(argument).AndReturn(to_return)

        self.mox.ReplayAll()
        self.assertEquals(self.dev_server.get_control_file(name, file),
                          contents)

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testGetControlFileSSH(self):
        """Should successfully get a control file from the dev server using
        ssh."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = True

        name = 'fake/build'
        file = 'file/one'
        contents = 'Multi-line\nControl File Contents\n'
        argument = mox.And(mox.StrContains(self._HOST),
                            mox.StrContains(name),
                            mox.StrContains(file))
        to_return = MockSshResponse(contents)
        utils.run(argument, timeout=mox.IgnoreArg()).AndReturn(to_return)

        self.mox.ReplayAll()
        self.assertEquals(self.dev_server.get_control_file(name, file),
                          contents)

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testErrorGetControlFile(self):
        """Should try to get the contents of a control file using http, get
        exception."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        self._returnHttpServerError()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.get_control_file,
                          '', '')

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testForbiddenGetControlFile(self):
        """Should try to get the contents of a control file using http, get
        exception."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        self._returnHttpForbidden()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.get_control_file,
                          '', '')

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testCmdErrorGetControlFile(self):
        """Should try to get the contents of a control file using ssh, get
        exception."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = True

        self._returnCmdError()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.get_control_file,
                          '', '')

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testGetLatestBuildHTTP(self):
        """Should successfully return a build for a given target using http."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        self.mox.StubOutWithMock(dev_server.ImageServer, 'servers')
        self.mox.StubOutWithMock(dev_server.DevServer, 'devserver_healthy')

        dev_server.ImageServer.servers().AndReturn([self._HOST])
        dev_server.ImageServer.devserver_healthy(self._HOST).AndReturn(True)

        target = 'x86-generic-release'
        build_string = 'R18-1586.0.0-a1-b1514'
        argument = mox.And(mox.StrContains(self._HOST),
                           mox.StrContains(target))
        to_return = StringIO.StringIO(build_string)
        urllib2.urlopen(argument).AndReturn(to_return)

        self.mox.ReplayAll()
        build = dev_server.ImageServer.get_latest_build(target)
        self.assertEquals(build_string, build)

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testGetLatestBuildSSH(self):
        """Should successfully return a build for a given target using ssh."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = True

        self.mox.StubOutWithMock(dev_server.ImageServer, 'servers')
        self.mox.StubOutWithMock(dev_server.DevServer, 'devserver_healthy')

        dev_server.ImageServer.servers().AndReturn([self._HOST])
        dev_server.ImageServer.devserver_healthy(self._HOST).AndReturn(True)

        target = 'x86-generic-release'
        build_string = 'R18-1586.0.0-a1-b1514'
        argument = mox.And(mox.StrContains(self._HOST),
                           mox.StrContains(target))
        to_return = MockSshResponse(build_string)
        utils.run(argument, timeout=mox.IgnoreArg()).AndReturn(to_return)

        self.mox.ReplayAll()
        build = dev_server.ImageServer.get_latest_build(target)
        self.assertEquals(build_string, build)

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testGetLatestBuildWithManyDevserversHTTP(self):
        """Should successfully return newest build with multiple devservers
        using http."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        self.mox.StubOutWithMock(dev_server.ImageServer, 'servers')
        self.mox.StubOutWithMock(dev_server.DevServer, 'devserver_healthy')

        host0_expected = 'http://host0:8080'
        host1_expected = 'http://host1:8082'

        dev_server.ImageServer.servers().MultipleTimes().AndReturn(
                [host0_expected, host1_expected])

        dev_server.ImageServer.devserver_healthy(host0_expected).AndReturn(True)
        dev_server.ImageServer.devserver_healthy(host1_expected).AndReturn(True)

        target = 'x86-generic-release'
        build_string1 = 'R9-1586.0.0-a1-b1514'
        build_string2 = 'R19-1586.0.0-a1-b3514'
        argument1 = mox.And(mox.StrContains(host0_expected),
                            mox.StrContains(target))
        argument2 = mox.And(mox.StrContains(host1_expected),
                            mox.StrContains(target))
        to_return1 = StringIO.StringIO(build_string1)
        to_return2 = StringIO.StringIO(build_string2)
        urllib2.urlopen(argument1).AndReturn(to_return1)
        urllib2.urlopen(argument2).AndReturn(to_return2)

        self.mox.ReplayAll()
        build = dev_server.ImageServer.get_latest_build(target)
        self.assertEquals(build_string2, build)

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testGetLatestBuildWithManyDevserversSSH(self):
        """Should successfully return newest build with multiple devservers
        using http."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = True

        self.mox.StubOutWithMock(dev_server.ImageServer, 'servers')
        self.mox.StubOutWithMock(dev_server.DevServer, 'devserver_healthy')

        host0_expected = 'http://host0:8080'
        host1_expected = 'http://host1:8082'

        dev_server.ImageServer.servers().MultipleTimes().AndReturn(
                [host0_expected, host1_expected])

        dev_server.ImageServer.devserver_healthy(host0_expected).AndReturn(True)
        dev_server.ImageServer.devserver_healthy(host1_expected).AndReturn(True)

        target = 'x86-generic-release'
        build_string1 = 'R9-1586.0.0-a1-b1514'
        build_string2 = 'R19-1586.0.0-a1-b3514'
        argument1 = mox.And(mox.StrContains(host0_expected),
                            mox.StrContains(target))
        argument2 = mox.And(mox.StrContains(host1_expected),
                            mox.StrContains(target))
        to_return1 = MockSshResponse(build_string1)
        to_return2 = MockSshResponse(build_string2)
        utils.run(argument1, timeout=mox.IgnoreArg()).AndReturn(to_return1)
        utils.run(argument2, timeout=mox.IgnoreArg()).AndReturn(to_return2)

        self.mox.ReplayAll()
        build = dev_server.ImageServer.get_latest_build(target)
        self.assertEquals(build_string2, build)

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testCrashesAreSetToTheCrashServer(self):
        """Should send symbolicate dump rpc calls to crash_server."""
        self.mox.ReplayAll()
        call = self.crash_server.build_call('symbolicate_dump')
        self.assertTrue(call.startswith(self._CRASH_HOST))


    def _stageTestHelperHTTP(self, artifacts=[], files=[], archive_url=None):
        """Helper to test combos of files/artifacts/urls with stage call
        using http."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        expected_archive_url = archive_url
        if not archive_url:
            expected_archive_url = 'gs://my_default_url'
            self.mox.StubOutWithMock(dev_server, '_get_image_storage_server')
            dev_server._get_image_storage_server().AndReturn(
                'gs://my_default_url')
            name = 'fake/image'
        else:
            # This is embedded in the archive_url. Not needed.
            name = ''

        argument1 = mox.And(mox.StrContains(expected_archive_url),
                            mox.StrContains(name),
                            mox.StrContains('artifacts=%s' %
                                            ','.join(artifacts)),
                            mox.StrContains('files=%s' % ','.join(files)),
                            mox.StrContains('stage?'))
        argument2 = mox.And(mox.StrContains(expected_archive_url),
                            mox.StrContains(name),
                            mox.StrContains('artifacts=%s' %
                                            ','.join(artifacts)),
                            mox.StrContains('files=%s' % ','.join(files)),
                            mox.StrContains('is_staged'))
        to_return = StringIO.StringIO('Success')
        urllib2.urlopen(argument1).AndReturn(to_return)
        to_return = StringIO.StringIO('True')
        urllib2.urlopen(argument2).AndReturn(to_return)

        self.mox.ReplayAll()
        self.dev_server.stage_artifacts(name, artifacts, files, archive_url)
        self.mox.VerifyAll()

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def _stageTestHelperSSH(self, artifacts=[], files=[], archive_url=None):
        """Helper to test combos of files/artifacts/urls with stage call
        using ssh."""
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = True

        expected_archive_url = archive_url
        if not archive_url:
            expected_archive_url = 'gs://my_default_url'
            self.mox.StubOutWithMock(dev_server, '_get_image_storage_server')
            dev_server._get_image_storage_server().AndReturn(
                'gs://my_default_url')
            name = 'fake/image'
        else:
            # This is embedded in the archive_url. Not needed.
            name = ''

        argument1 = mox.And(mox.StrContains(expected_archive_url),
                            mox.StrContains(name),
                            mox.StrContains('artifacts=%s' %
                                            ','.join(artifacts)),
                            mox.StrContains('files=%s' % ','.join(files)),
                            mox.StrContains('stage?'))
        argument2 = mox.And(mox.StrContains(expected_archive_url),
                            mox.StrContains(name),
                            mox.StrContains('artifacts=%s' %
                                            ','.join(artifacts)),
                            mox.StrContains('files=%s' % ','.join(files)),
                            mox.StrContains('is_staged'))
        to_return = MockSshResponse('Success')
        utils.run(argument1, timeout=mox.IgnoreArg()).AndReturn(to_return)
        to_return = MockSshResponse('True')
        utils.run(argument2, timeout=mox.IgnoreArg()).AndReturn(to_return)

        self.mox.ReplayAll()
        self.dev_server.stage_artifacts(name, artifacts, files, archive_url)
        self.mox.VerifyAll()

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testStageArtifactsBasicHTTP(self):
        """Basic functionality to stage artifacts using http (similar to
        trigger_download)."""
        self._stageTestHelperHTTP(artifacts=['full_payload', 'stateful'])


    def testStageArtifactsBasicSSH(self):
        """Basic functionality to stage artifacts using ssh (similar to
        trigger_download)."""
        self._stageTestHelperSSH(artifacts=['full_payload', 'stateful'])


    def testStageArtifactsBasicWithFilesHTTP(self):
        """Basic functionality to stage artifacts using http (similar to
        trigger_download)."""
        self._stageTestHelperHTTP(artifacts=['full_payload', 'stateful'],
                                  files=['taco_bell.coupon'])


    def testStageArtifactsBasicWithFilesSSH(self):
        """Basic functionality to stage artifacts using ssh (similar to
        trigger_download)."""
        self._stageTestHelperSSH(artifacts=['full_payload', 'stateful'],
                                 files=['taco_bell.coupon'])


    def testStageArtifactsOnlyFilesHTTP(self):
        """Test staging of only file artifacts using http."""
        self._stageTestHelperHTTP(files=['tasty_taco_bell.coupon'])


    def testStageArtifactsOnlyFilesSSH(self):
        """Test staging of only file artifacts using ssh."""
        self._stageTestHelperSSH(files=['tasty_taco_bell.coupon'])


    def testStageWithArchiveURLHTTP(self):
        """Basic functionality to stage artifacts using http (similar to
        trigger_download)."""
        self._stageTestHelperHTTP(files=['tasty_taco_bell.coupon'],
                                  archive_url='gs://tacos_galore/my/dir')


    def testStageWithArchiveURLSSH(self):
        """Basic functionality to stage artifacts using ssh (similar to
        trigger_download)."""
        self._stageTestHelperSSH(files=['tasty_taco_bell.coupon'],
                                 archive_url='gs://tacos_galore/my/dir')


    def testStagedFileUrl(self):
        """Sanity tests that the staged file url looks right."""
        devserver_label = 'x86-mario-release/R30-1234.0.0'
        url = self.dev_server.get_staged_file_url('stateful.tgz',
                                                  devserver_label)
        expected_url = '/'.join([self._HOST, 'static', devserver_label,
                                 'stateful.tgz'])
        self.assertEquals(url, expected_url)

        devserver_label = 'something_crazy/that/you_MIGHT/hate'
        url = self.dev_server.get_staged_file_url('chromiumos_image.bin',
                                                  devserver_label)
        expected_url = '/'.join([self._HOST, 'static', devserver_label,
                                 'chromiumos_image.bin'])
        self.assertEquals(url, expected_url)


    def _StageTimeoutHelper(self):
        """Helper class for testing staging timeout."""
        self.mox.StubOutWithMock(dev_server.ImageServer, 'call_and_wait')
        dev_server.ImageServer.call_and_wait(
                call_name='stage',
                artifacts=mox.IgnoreArg(),
                files=mox.IgnoreArg(),
                archive_url=mox.IgnoreArg(),
                error_message=mox.IgnoreArg()).AndRaise(error.TimeoutException)


    def test_StageArtifactsTimeout(self):
        """Test DevServerException is raised when stage_artifacts timed out."""
        self._StageTimeoutHelper()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.stage_artifacts,
                          image='fake/image', artifacts=['full_payload'])
        self.mox.VerifyAll()


    def test_TriggerDownloadTimeout(self):
        """Test DevServerException is raised when trigger_download timed out."""
        self._StageTimeoutHelper()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.trigger_download,
                          image='fake/image')
        self.mox.VerifyAll()


    def test_FinishDownloadTimeout(self):
        """Test DevServerException is raised when finish_download timed out."""
        self._StageTimeoutHelper()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.finish_download,
                          image='fake/image')
        self.mox.VerifyAll()


    def test_compare_load(self):
        """Test load comparison logic.
        """
        load_high_cpu = {'devserver': 'http://devserver_1:8082',
                         dev_server.DevServer.CPU_LOAD: 100.0,
                         dev_server.DevServer.NETWORK_IO: 1024*1024*1.0,
                         dev_server.DevServer.DISK_IO: 1024*1024.0}
        load_high_network = {'devserver': 'http://devserver_1:8082',
                             dev_server.DevServer.CPU_LOAD: 1.0,
                             dev_server.DevServer.NETWORK_IO: 1024*1024*100.0,
                             dev_server.DevServer.DISK_IO: 1024*1024*1.0}
        load_1 = {'devserver': 'http://devserver_1:8082',
                  dev_server.DevServer.CPU_LOAD: 1.0,
                  dev_server.DevServer.NETWORK_IO: 1024*1024*1.0,
                  dev_server.DevServer.DISK_IO: 1024*1024*2.0}
        load_2 = {'devserver': 'http://devserver_1:8082',
                  dev_server.DevServer.CPU_LOAD: 1.0,
                  dev_server.DevServer.NETWORK_IO: 1024*1024*1.0,
                  dev_server.DevServer.DISK_IO: 1024*1024*1.0}
        self.assertFalse(dev_server._is_load_healthy(load_high_cpu))
        self.assertFalse(dev_server._is_load_healthy(load_high_network))
        self.assertTrue(dev_server._compare_load(load_1, load_2) > 0)


    def _testSuccessfulTriggerDownloadAndroidHTTP(self, synchronous=True):
        """Call the dev server's download method using http with given
        synchronous setting.

        @param synchronous: True to call the download method synchronously.
        """
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        target = 'test_target'
        branch = 'test_branch'
        build_id = '123456'
        self.mox.StubOutWithMock(dev_server.AndroidBuildServer,
                                 '_finish_download')
        argument1 = mox.And(mox.StrContains(self._HOST),
                            mox.StrContains(target),
                            mox.StrContains(branch),
                            mox.StrContains(build_id),
                            mox.StrContains('stage?'))
        argument2 = mox.And(mox.StrContains(self._HOST),
                            mox.StrContains(target),
                            mox.StrContains(branch),
                            mox.StrContains(build_id),
                            mox.StrContains('is_staged'))
        to_return = StringIO.StringIO('Success')
        urllib2.urlopen(argument1).AndReturn(to_return)
        to_return = StringIO.StringIO('True')
        urllib2.urlopen(argument2).AndReturn(to_return)

        if synchronous:
            android_build_info = {'target': target,
                                  'build_id': build_id,
                                  'branch': branch}
            build = dev_server.ANDROID_BUILD_NAME_PATTERN % android_build_info
            self.android_dev_server._finish_download(
                    build,
                    dev_server._ANDROID_ARTIFACTS_TO_BE_STAGED_FOR_IMAGE, '',
                    target=target, build_id=build_id, branch=branch)

        # Synchronous case requires a call to finish download.
        self.mox.ReplayAll()
        self.android_dev_server.trigger_download(
                synchronous=synchronous, target=target, build_id=build_id,
                branch=branch)
        self.mox.VerifyAll()

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def _testSuccessfulTriggerDownloadAndroidSSH(self, synchronous=True):
        """Call the dev server's download method using ssh with given
        synchronous setting.

        @param synchronous: True to call the download method synchronously.
        """
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = True

        target = 'test_target'
        branch = 'test_branch'
        build_id = '123456'
        self.mox.StubOutWithMock(dev_server.AndroidBuildServer,
                                 '_finish_download')
        argument1 = mox.And(mox.StrContains(self._HOST),
                            mox.StrContains(target),
                            mox.StrContains(branch),
                            mox.StrContains(build_id),
                            mox.StrContains('stage?'))
        argument2 = mox.And(mox.StrContains(self._HOST),
                            mox.StrContains(target),
                            mox.StrContains(branch),
                            mox.StrContains(build_id),
                            mox.StrContains('is_staged'))
        to_return = MockSshResponse('Success')
        utils.run(argument1, timeout=mox.IgnoreArg()).AndReturn(to_return)
        to_return = MockSshResponse('True')
        utils.run(argument2, timeout=mox.IgnoreArg()).AndReturn(to_return)

        if synchronous:
            android_build_info = {'target': target,
                                  'build_id': build_id,
                                  'branch': branch}
            build = dev_server.ANDROID_BUILD_NAME_PATTERN % android_build_info
            self.android_dev_server._finish_download(
                    build,
                    dev_server._ANDROID_ARTIFACTS_TO_BE_STAGED_FOR_IMAGE, '',
                    target=target, build_id=build_id, branch=branch)

        # Synchronous case requires a call to finish download.
        self.mox.ReplayAll()
        self.android_dev_server.trigger_download(
                synchronous=synchronous, target=target, build_id=build_id,
                branch=branch)
        self.mox.VerifyAll()

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testSuccessfulTriggerDownloadAndroidSyncHTTP(self):
        """Call the dev server's download method using http with
        synchronous=True."""
        self._testSuccessfulTriggerDownloadAndroidHTTP(synchronous=True)


    def testSuccessfulTriggerDownloadAndroidSyncSSH(self):
        """Call the dev server's download method using http with
        synchronous=True."""
        self._testSuccessfulTriggerDownloadAndroidSSH(synchronous=True)


    def testSuccessfulTriggerDownloadAndroidAsyncHTTP(self):
        """Call the dev server's download method using http with
        synchronous=False."""
        self._testSuccessfulTriggerDownloadAndroidHTTP(synchronous=False)


    def testSuccessfulTriggerDownloadAndroidAsyncSSH(self):
        """Call the dev server's download method using ssh with
        synchronous=False."""
        self._testSuccessfulTriggerDownloadAndroidSSH(synchronous=False)


    def testGetUnrestrictedDevservers(self):
        """Test method get_unrestricted_devservers works as expected."""
        restricted_devserver = 'http://192.168.0.100:8080'
        unrestricted_devserver = 'http://172.1.1.3:8080'
        self.mox.StubOutWithMock(dev_server.ImageServer, 'servers')
        dev_server.ImageServer.servers().AndReturn([restricted_devserver,
                                                    unrestricted_devserver])
        self.mox.ReplayAll()
        self.assertEqual(dev_server.ImageServer.get_unrestricted_devservers(
                                [('192.168.0.0', 24)]),
                         [unrestricted_devserver])


    def testDevserverHealthyHTTP(self):
        """Test which types of connectiions that method devserver_healthy uses
        for different types of DevServer.

        CrashServer always use http call.
        ImageServer and AndriodBuildServer use http call since
        enable_ssh_connection_for_devserver=False.
        """
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        argument = mox.StrContains(self._HOST)

        # for testing CrashServer
        to_return = StringIO.StringIO('{"free_disk": 1024}')
        urllib2.urlopen(argument, data=None).AndReturn(to_return)
        # for testing ImageServer
        to_return = StringIO.StringIO('{"free_disk": 1024}')
        urllib2.urlopen(argument, data=None).AndReturn(to_return)
        # for testing AndroidBuildServer
        to_return = StringIO.StringIO('{"free_disk": 1024}')
        urllib2.urlopen(argument, data=None).AndReturn(to_return)

        self.mox.ReplayAll()
        self.assertTrue(dev_server.CrashServer.devserver_healthy(self._HOST))
        self.assertTrue(dev_server.ImageServer.devserver_healthy(self._HOST))
        self.assertTrue(
                dev_server.AndroidBuildServer.devserver_healthy(self._HOST))

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testDevserverHealthySSH(self):
        """Test which types of connectiions that method devserver_healthy uses
        for different types of DevServer.

        CrashServer always use http call.
        ImageServer and AndriodBuildServer use ssh call since
        enable_ssh_connection_for_devserver=True.
        """
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = True

        argument = mox.StrContains(self._HOST)

        # for testing CrashServer
        to_return = StringIO.StringIO('{"free_disk": 1024}')
        urllib2.urlopen(argument, data=None).AndReturn(to_return)
        # for testing ImageServer
        to_return = MockSshResponse('{"free_disk": 1024}')
        utils.run(argument, timeout=mox.IgnoreArg()).AndReturn(to_return)
        # for testing AndroidBuildServer
        utils.run(argument, timeout=mox.IgnoreArg()).AndReturn(to_return)

        self.mox.ReplayAll()
        self.assertTrue(dev_server.CrashServer.devserver_healthy(self._HOST))
        self.assertTrue(dev_server.ImageServer.devserver_healthy(self._HOST))
        self.assertTrue(
                dev_server.AndroidBuildServer.devserver_healthy(self._HOST))

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testLocateFileHTTP(self):
        """Test which types of connectiions that method devserver_healthy uses
        for different types of DevServer.

        CrashServer always use http call.
        ImageServer and AndriodBuildServer use ssh call since
        enable_ssh_connection_for_devserver=True.
        """
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = False

        file_name = 'fake_file'
        artifacts=['full_payload', 'stateful']
        build = 'fake_build'
        argument = mox.And(mox.StrContains(file_name),
                            mox.StrContains(build),
                            mox.StrContains('locate_file'))
        to_return = StringIO.StringIO('file_path')
        urllib2.urlopen(argument).AndReturn(to_return)

        self.mox.ReplayAll()
        file_location = 'http://nothing/static/fake_build/file_path'
        self.assertEqual(self.android_dev_server.locate_file(
                file_name, artifacts, build, None), file_location)

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


    def testLocateFileSSH(self):
        """Test which types of connectiions that method devserver_healthy uses
        for different types of DevServer.

        CrashServer always use http call.
        ImageServer and AndriodBuildServer use ssh call since
        enable_ssh_connection_for_devserver=True.
        """
        save_ssh_config = dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER
        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = True

        file_name = 'fake_file'
        artifacts=['full_payload', 'stateful']
        build = 'fake_build'
        argument = mox.And(mox.StrContains(file_name),
                            mox.StrContains(build),
                            mox.StrContains('locate_file'))
        to_return = MockSshResponse('file_path')
        utils.run(argument, timeout=mox.IgnoreArg()).AndReturn(to_return)

        self.mox.ReplayAll()
        file_location = 'http://nothing/static/fake_build/file_path'
        self.assertEqual(self.android_dev_server.locate_file(
                file_name, artifacts, build, None), file_location)

        dev_server.ENABLE_SSH_CONNECTION_FOR_DEVSERVER = save_ssh_config


if __name__ == "__main__":
    unittest.main()
