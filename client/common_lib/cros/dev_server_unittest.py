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

    def setUp(self):
        super(DevServerTest, self).setUp()
        self.dev_server = dev_server.DevServer(self._HOST)


    def testSuccessfulTriggerDownload(self):
        """Should successfully call the dev server's download method."""
        name = 'fake/image'
        self.mox.StubOutWithMock(urllib2, 'urlopen')
        to_return = StringIO.StringIO('Success')
        urllib2.urlopen(mox.And(mox.StrContains(self._HOST),
                                mox.StrContains(name))).AndReturn(to_return)
        self.mox.ReplayAll()
        self.assertTrue(self.dev_server.trigger_download(name))


    def testFailedTriggerDownload(self):
        """Should call the dev server's download method, fail gracefully."""
        self.mox.StubOutWithMock(urllib2, 'urlopen')
        to_raise = urllib2.HTTPError(url='',
                                     code=httplib.INTERNAL_SERVER_ERROR,
                                     msg='',
                                     hdrs=None,
                                     fp=None)
        urllib2.urlopen(mox.IgnoreArg()).AndRaise(to_raise)
        self.mox.ReplayAll()
        self.assertFalse(self.dev_server.trigger_download(''))


    def testExplodingTriggerDownload(self):
        """Should call the dev server's download method, get exception."""
        self.mox.StubOutWithMock(urllib2, 'urlopen')
        to_raise = urllib2.HTTPError(url='',
                                     code=httplib.FORBIDDEN,
                                     msg='',
                                     hdrs=None,
                                     fp=None)
        urllib2.urlopen(mox.IgnoreArg()).AndRaise(to_raise)
        self.mox.ReplayAll()
        self.assertRaises(urllib2.HTTPError,
                          self.dev_server.trigger_download,
                          '')
