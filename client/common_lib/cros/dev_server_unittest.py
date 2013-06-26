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
import urllib2

from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.client.common_lib.cros import retry

def retry_mock(ExceptionToCheck, timeout_min):
  """A mock retry decorator to use in place of the actual one for testing."""
  def inner_retry(func):
    return func

  return inner_retry


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
        self.mox.StubOutWithMock(urllib2, 'urlopen')


    def testSimpleResolve(self):
        """One devserver, verify we resolve to it."""
        self.mox.StubOutWithMock(dev_server, '_get_dev_server_list')
        self.mox.StubOutWithMock(dev_server.DevServer, 'devserver_healthy')
        dev_server._get_dev_server_list().AndReturn([DevServerTest._HOST])
        dev_server.DevServer.devserver_healthy(DevServerTest._HOST).AndReturn(
                                                                        True)
        self.mox.ReplayAll()
        devserver = dev_server.ImageServer.resolve('my_build')
        self.assertEquals(devserver.url(), DevServerTest._HOST)


    def testResolveWithFailure(self):
        """Ensure we rehash on a failed ping on a bad_host."""
        self.mox.StubOutWithMock(dev_server, '_get_dev_server_list')
        bad_host, good_host = 'http://bad_host:99', 'http://good_host:8080'
        dev_server._get_dev_server_list().AndReturn([bad_host, good_host])

        # Mock out bad ping failure to bad_host by raising devserver exception.
        urllib2.urlopen(mox.StrContains(bad_host), data=None).AndRaise(
                dev_server.DevServerException())
        # Good host is good.
        to_return = StringIO.StringIO('{"free_disk": 1024}')
        urllib2.urlopen(mox.StrContains(good_host), data=None).AndReturn(to_return)

        self.mox.ReplayAll()
        host = dev_server.ImageServer.resolve(0) # Using 0 as it'll hash to 0.
        self.assertEquals(host.url(), good_host)
        self.mox.VerifyAll()


    def testResolveWithFailureURLError(self):
        """Ensure we rehash on a failed ping on a bad_host after urlerror."""
        # Retry mock just return the original method.
        retry.retry = retry_mock
        self.mox.StubOutWithMock(dev_server, '_get_dev_server_list')
        bad_host, good_host = 'http://bad_host:99', 'http://good_host:8080'
        dev_server._get_dev_server_list().AndReturn([bad_host, good_host])

        # Mock out bad ping failure to bad_host by raising devserver exception.
        urllib2.urlopen(mox.StrContains(bad_host),
                data=None).MultipleTimes().AndRaise(
                        urllib2.URLError('urlopen connection timeout'))

        # Good host is good.
        to_return = StringIO.StringIO('{"free_disk": 1024}')
        urllib2.urlopen(mox.StrContains(good_host),
                data=None).AndReturn(to_return)

        self.mox.ReplayAll()
        host = dev_server.ImageServer.resolve(0) # Using 0 as it'll hash to 0.
        self.assertEquals(host.url(), good_host)
        self.mox.VerifyAll()


    def testResolveWithManyDevservers(self):
        """Should be able to return different urls with multiple devservers."""
        self.mox.StubOutWithMock(dev_server.ImageServer, 'servers')
        self.mox.StubOutWithMock(dev_server.DevServer, 'devserver_healthy')

        host0_expected = 'http://host0:8080'
        host1_expected = 'http://host1:8082'

        dev_server.ImageServer.servers().MultipleTimes().AndReturn(
                [host0_expected, host1_expected])
        dev_server.DevServer.devserver_healthy(host0_expected).AndReturn(True)
        dev_server.DevServer.devserver_healthy(host1_expected).AndReturn(True)

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


    def testSuccessfulTriggerDownloadSync(self):
        """Call the dev server's download method with synchronous=True."""
        name = 'fake/image'
        self.mox.StubOutWithMock(dev_server.ImageServer, 'finish_download')
        to_return = StringIO.StringIO('Success')
        urllib2.urlopen(mox.And(mox.StrContains(self._HOST),
                                mox.StrContains(name))).AndReturn(to_return)
        self.dev_server.finish_download(name)

        # Synchronous case requires a call to finish download.
        self.mox.ReplayAll()
        self.dev_server.trigger_download(name, synchronous=True)
        self.mox.VerifyAll()


    def testSuccessfulTriggerDownloadASync(self):
        """Call the dev server's download method with synchronous=False."""
        name = 'fake/image'
        to_return = StringIO.StringIO('Success')
        urllib2.urlopen(mox.And(mox.StrContains(self._HOST),
                                mox.StrContains(name))).AndReturn(to_return)

        self.mox.ReplayAll()
        self.dev_server.trigger_download(name, synchronous=False)
        self.mox.VerifyAll()


    def testURLErrorRetryTriggerDownload(self):
        """Should retry on URLError, but pass through real exception."""
        self.mox.StubOutWithMock(time, 'sleep')

        refused = urllib2.URLError('[Errno 111] Connection refused')
        urllib2.urlopen(mox.IgnoreArg()).AndRaise(refused)
        time.sleep(mox.IgnoreArg())
        self._returnHttpForbidden()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.trigger_download,
                          '')


    def testErrorTriggerDownload(self):
        """Should call the dev server's download method, fail gracefully."""
        self._returnHttpServerError()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.trigger_download,
                          '')


    def testForbiddenTriggerDownload(self):
        """Should call the dev server's download method, get exception."""
        self._returnHttpForbidden()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.trigger_download,
                          '')


    def testSuccessfulFinishDownload(self):
        """Should successfully call the dev server's finish download method."""
        name = 'fake/image'
        to_return = StringIO.StringIO('Success')
        urllib2.urlopen(mox.And(mox.StrContains(self._HOST),
                                mox.StrContains(name))).AndReturn(to_return)

        # Synchronous case requires a call to finish download.
        self.mox.ReplayAll()
        self.dev_server.finish_download(name)  # Raises on failure.
        self.mox.VerifyAll()


    def testErrorFinishDownload(self):
        """Should call the dev server's finish download method, fail gracefully.
        """
        self._returnHttpServerError()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.finish_download,
                          '')


    def testListControlFiles(self):
        """Should successfully list control files from the dev server."""
        name = 'fake/build'
        control_files = ['file/one', 'file/two']
        to_return = StringIO.StringIO('\n'.join(control_files))
        urllib2.urlopen(mox.And(mox.StrContains(self._HOST),
                                mox.StrContains(name))).AndReturn(to_return)
        self.mox.ReplayAll()
        paths = self.dev_server.list_control_files(name)
        self.assertEquals(len(paths), 2)
        for f in control_files:
            self.assertTrue(f in paths)


    def testFailedListControlFiles(self):
        """Should call the dev server's list-files method, get exception."""
        self._returnHttpServerError()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.list_control_files,
                          '')


    def testExplodingListControlFiles(self):
        """Should call the dev server's list-files method, get exception."""
        self._returnHttpForbidden()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.list_control_files,
                          '')


    def testGetControlFile(self):
        """Should successfully get a control file from the dev server."""
        name = 'fake/build'
        file = 'file/one'
        contents = 'Multi-line\nControl File Contents\n'
        to_return = StringIO.StringIO(contents)
        urllib2.urlopen(mox.And(mox.StrContains(self._HOST),
                                mox.StrContains(name),
                                mox.StrContains(file))).AndReturn(to_return)
        self.mox.ReplayAll()
        self.assertEquals(self.dev_server.get_control_file(name, file),
                          contents)


    def testErrorGetControlFile(self):
        """Should try to get the contents of a control file, get exception."""
        self._returnHttpServerError()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.get_control_file,
                          '', '')


    def testForbiddenGetControlFile(self):
        """Should try to get the contents of a control file, get exception."""
        self._returnHttpForbidden()
        self.mox.ReplayAll()
        self.assertRaises(dev_server.DevServerException,
                          self.dev_server.get_control_file,
                          '', '')


    def testGetLatestBuild(self):
        """Should successfully return a build for a given target."""
        self.mox.StubOutWithMock(dev_server.ImageServer, 'servers')
        self.mox.StubOutWithMock(dev_server.DevServer, 'devserver_healthy')

        dev_server.ImageServer.servers().AndReturn([self._HOST])
        dev_server.DevServer.devserver_healthy(self._HOST).AndReturn(True)

        target = 'x86-generic-release'
        build_string = 'R18-1586.0.0-a1-b1514'
        to_return = StringIO.StringIO(build_string)
        urllib2.urlopen(mox.And(mox.StrContains(self._HOST),
                                mox.StrContains(target))).AndReturn(to_return)
        self.mox.ReplayAll()
        build = dev_server.ImageServer.get_latest_build(target)
        self.assertEquals(build_string, build)


    def testGetLatestBuildWithManyDevservers(self):
        """Should successfully return newest build with multiple devservers."""
        self.mox.StubOutWithMock(dev_server.ImageServer, 'servers')
        self.mox.StubOutWithMock(dev_server.DevServer, 'devserver_healthy')

        host0_expected = 'http://host0:8080'
        host1_expected = 'http://host1:8082'

        dev_server.ImageServer.servers().MultipleTimes().AndReturn(
                [host0_expected, host1_expected])

        dev_server.DevServer.devserver_healthy(host0_expected).AndReturn(True)
        dev_server.DevServer.devserver_healthy(host1_expected).AndReturn(True)

        target = 'x86-generic-release'
        build_string1 = 'R9-1586.0.0-a1-b1514'
        build_string2 = 'R19-1586.0.0-a1-b3514'
        to_return1 = StringIO.StringIO(build_string1)
        to_return2 = StringIO.StringIO(build_string2)
        urllib2.urlopen(mox.And(mox.StrContains(host0_expected),
                                mox.StrContains(target))).AndReturn(to_return1)
        urllib2.urlopen(mox.And(mox.StrContains(host1_expected),
                                mox.StrContains(target))).AndReturn(to_return2)

        self.mox.ReplayAll()
        build = dev_server.ImageServer.get_latest_build(target)
        self.assertEquals(build_string2, build)


    def testCrashesAreSetToTheCrashServer(self):
        """Should send symbolicate dump rpc calls to crash_server."""
        hv = 'iliketacos'
        self.mox.ReplayAll()
        call = self.crash_server.build_call('symbolicate_dump')
        self.assertTrue(call.startswith(self._CRASH_HOST))

