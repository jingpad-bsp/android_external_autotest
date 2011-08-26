# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, httpd


class desktopui_UrlFetch(cros_ui_test.UITest):
    version = 1


    def initialize(self, live=True):
        self._live = live
        super(desktopui_UrlFetch, self).initialize(creds='$default')
        if live:
            self._test_url = 'http://www.noaa.gov/'
            self._expected_title = \
                'NOAA - National Oceanic and Atmospheric Administration'
        else:
            self._test_url = 'http://localhost:8000/hello.html'
            self._expected_title = 'Hello World'
            self._testServer = httpd.HTTPListener(8000, docroot=self.bindir)
            self._testServer.run()


    def cleanup(self):
        if not self._live:
            self._testServer.stop()
        super(desktopui_UrlFetch, self).cleanup()


    def start_authserver(self):
        # Do nothing in live mode so that we do real login.
        # In non-live mode, setup local authserver which handles login.
        if not self._live:
            super(desktopui_UrlFetch, self).start_authserver()


    def run_once(self):
        import pyauto

        assert not self.pyauto.GetCookie(pyauto.GURL(self._test_url))

        self.pyauto.NavigateToURL(self._test_url)
        tab_title = self.pyauto.GetActiveTabTitle()
        if tab_title != self._expected_title:
            raise error.TestError(
                'Unexpected web site title.  Expected: %s. '
                'Returned: %s' % (self._expected_title, tab_title))

        cookie = self.pyauto.GetCookie(pyauto.GURL(self._test_url))
        if not cookie:
            raise error.TestError('Expected cookie for %s' % self._test_url)
