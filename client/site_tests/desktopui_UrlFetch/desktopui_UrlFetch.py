# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.cros import pyauto_test


class desktopui_UrlFetch(pyauto_test.PyAutoTest):
    version = 1

    def run_once(self):
        url = 'http://www.youtube.com'
        cookie_expected = 'VISITOR_INFO1_LIVE2'

        self.pyauto.NavigateToURL(url)
        if self.pyauto.GetActiveTabTitle().split()[0] != 'YouTube':
            raise error.TestError('Unexpected web site title for YouTube')

        cookie = self.pyauto.GetCookie(self.pyauto.GURL(url))
        if cookie != cookie_expected:
            raise error.TestError('Unexpected cookie from YouTube')
