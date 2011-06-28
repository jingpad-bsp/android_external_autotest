# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import pyauto_test


class desktopui_UrlFetch(pyauto_test.PyAutoTest):
    version = 1

    def run_once(self):
        url = 'http://dev.chromium.org'
        import pyauto

        assert not self.pyauto.GetCookie(pyauto.GURL(url))

        self.pyauto.NavigateToURL(url)
        if self.pyauto.GetActiveTabTitle() != 'The Chromium Projects':
            raise error.TestError('Unexpected web site title.')

        cookie = self.pyauto.GetCookie(pyauto.GURL(url))
        if not cookie:
            raise error.TestError('Expected cookie for %s' % url)
