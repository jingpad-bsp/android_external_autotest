#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for client/common_lib/cros/dev_server.py."""

import httplib
import logging
import mox
import StringIO
import unittest
import urllib2

from autotest_lib.client.common_lib.cros import dev_server


class DevServerTest(mox.MoxTestBase):
    """Unit tests for dev_server.DevServer.

    @var _HOST: fake dev server host address.
    """

    _HOST = 'http://nothing'
    _CRASH_HOST = 'http://nothing-crashed'

    def setUp(self):
        super(DevServerTest, self).setUp()
        self.dev_server = dev_server.DevServer(self._HOST, self._CRASH_HOST)


    def _returnHttpServerError(self):
        self.mox.StubOutWithMock(urllib2, 'urlopen')
        e500 = urllib2.HTTPError(url='',
                                 code=httplib.INTERNAL_SERVER_ERROR,
                                 msg='',
                                 hdrs=None,
                                 fp=StringIO.StringIO('Expected.'))
        urllib2.urlopen(mox.IgnoreArg()).AndRaise(e500)


    def _returnHttpForbidden(self):
        self.mox.StubOutWithMock(urllib2, 'urlopen')
        e403 = urllib2.HTTPError(url='',
                                 code=httplib.FORBIDDEN,
                                 msg='',
                                 hdrs=None,
                                 fp=StringIO.StringIO('Expected.'))
        urllib2.urlopen(mox.IgnoreArg()).AndRaise(e403)


    def testSuccessfulTriggerDownloadSync(self):
        """Call the dev server's download method with synchronous=True."""
        name = 'fake/image'
        self.mox.StubOutWithMock(urllib2, 'urlopen')
        self.mox.StubOutWithMock(dev_server.DevServer, 'finish_download')
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
        self.mox.StubOutWithMock(urllib2, 'urlopen')
        self.mox.StubOutWithMock(dev_server.DevServer, 'finish_download')
        to_return = StringIO.StringIO('Success')
        urllib2.urlopen(mox.And(mox.StrContains(self._HOST),
                                mox.StrContains(name))).AndReturn(to_return)

        self.mox.ReplayAll()
        self.dev_server.trigger_download(name, synchronous=False)
        self.mox.VerifyAll()


    def testErrorTriggerDownload(self):
        """Should call the dev server's download method, fail gracefully."""
        self._returnHttpForbidden()
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
        self.mox.StubOutWithMock(urllib2, 'urlopen')
        to_return = StringIO.StringIO('Success')
        urllib2.urlopen(mox.And(mox.StrContains(self._HOST),
                                mox.StrContains(name))).AndReturn(to_return)

        # Synchronous case requires a call to finish download.
        self.mox.ReplayAll()
        self.dev_server.finish_download(name)  # Raises on failure.
        self.mox.VerifyAll()


    def testErrorTriggerDownload(self):
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
        self.mox.StubOutWithMock(urllib2, 'urlopen')
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
        self.mox.StubOutWithMock(urllib2, 'urlopen')
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
        target = 'x86-generic-release'
        build_string = 'R18-1586.0.0-a1-b1514'
        self.mox.StubOutWithMock(urllib2, 'urlopen')
        to_return = StringIO.StringIO(build_string)
        urllib2.urlopen(mox.And(mox.StrContains(self._HOST),
                                mox.StrContains(target))).AndReturn(to_return)
        self.mox.ReplayAll()
        build = self.dev_server.get_latest_build(target)
        self.assertEquals(build_string, build)


    def testThatWeCorrectlyReHashToTheSameDevserver(self):
        """Ensure calls with same hashing_value go to the same devserver."""
        for index in range(10):
          self.dev_server._dev_servers.append('http://nothing_%d' % index)

        method_name = 'my_method'
        hv1 = 'iliketacos'
        hv2 = 'iliketacos'
        hv3 = 'idontliketacos :('
        hv4 = 'idontliketacos :('

        call1 = self.dev_server._build_call(method_name, hashing_value=hv1)
        call2 = self.dev_server._build_call(method_name, hashing_value=hv2,
                                            some_arg='value')
        call3 = self.dev_server._build_call(method_name, hashing_value=hv3)
        call4 = self.dev_server._build_call(method_name, hashing_value=hv4,
                                            some_arg='value')

        self.assertTrue(call2.startswith(call1))
        self.assertTrue(call4.startswith(call3))


    def testGetLatestBuildWithManyDevservers(self):
        """Should successfully return newest build with multiple devservers."""
        self.dev_server._dev_servers.append('http://nothing_2')
        self.dev_server._dev_servers.append('http://nothing_3')
        target = 'x86-generic-release'
        build_string1 = 'R9-1586.0.0-a1-b1514'
        build_string2 = 'R19-1586.0.0-a1-b3514'
        build_string3 = 'R18-1486.0.0-a1-b2514'
        self.mox.StubOutWithMock(urllib2, 'urlopen')
        to_return1 = StringIO.StringIO(build_string1)
        to_return2 = StringIO.StringIO(build_string2)
        to_return3 = StringIO.StringIO(build_string3)
        urllib2.urlopen(mox.And(mox.StrContains(self._HOST),
                                mox.StrContains(target))).AndReturn(to_return1)
        urllib2.urlopen(mox.And(mox.StrContains(self._HOST),
                                mox.StrContains(target))).AndReturn(to_return2)
        urllib2.urlopen(mox.And(mox.StrContains(self._HOST),
                                mox.StrContains(target))).AndReturn(to_return3)

        self.mox.ReplayAll()
        build = self.dev_server.get_latest_build(target)
        self.assertEquals(build_string2, build)


    def testCrashesAreSetToTheCrashServer(self):
        """Should send symbolicate dump rpc calls to crash_server."""
        hv = 'iliketacos'
        self.mox.ReplayAll()
        call = self.dev_server._build_call('symbolicate_dump', hashing_value=hv)
        self.assertTrue(call.startswith(self._CRASH_HOST))
