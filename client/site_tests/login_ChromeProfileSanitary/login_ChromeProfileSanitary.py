# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import errno, logging, os, stat, time
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants, cros_ui, cros_ui_test
from autotest_lib.client.cros import httpd, login, pyauto_test

def respond_with_cookies(handler, url_args):
    """Responds with a Set-Cookie header to any GET request, and redirects
    to a chosen URL.
    """
    handler.send_response(303)
    handler.send_header('Set-Cookie', 'name=value')
    handler.send_header('Location', url_args['continue'][0])
    handler.end_headers()
    handler.wfile.write('Got form data:\n')
    handler.wfile.write('%s:\n' % url_args)


class login_ChromeProfileSanitary(cros_ui_test.UITest):
    version = 1


    def __get_cookies_mtime(self):
        try:
            cookies_info = os.stat(constants.LOGIN_PROFILE + '/Cookies')
            return cookies_info[stat.ST_MTIME]
        except OSError as e:
            if e.errno == errno.ENOENT:
                return None
            raise


    def initialize(self, creds='$default', **dargs):
        spec = 'http://localhost:8000'
        path = '/set_cookie'
        self._wait_path = '/test_over'
        self._test_url = spec + path + '?continue=' + spec + self._wait_path
        self._testServer = httpd.HTTPListener(8000, docroot=self.srcdir)
        self._testServer.add_url_handler('/set_cookie', respond_with_cookies)
        self._testServer.run()
        super(login_ChromeProfileSanitary, self).initialize(creds, **dargs)


    def cleanup(self):
        self._testServer.stop()
        cros_ui_test.UITest.cleanup(self)


    def run_once(self, timeout=10):
        # Get Default/Cookies mtime.
        cookies_mtime = self.__get_cookies_mtime()

        # Wait for chrome to show, then "crash" it.
        utils.nuke_process_by_name(constants.BROWSER, with_prejudice=True)

        # Re-connect to automation channel.
        self.pyauto.setUp()

        # Navigate to site that leaves cookies.
        if not self.logged_in():
            raise error.TestError('Logged out unexpectedly!')
        latch = self._testServer.add_wait_url(self._wait_path)
        self.pyauto.NavigateToURL(self._test_url)
        latch.wait(timeout)  # Redundant, but not a problem.
        if not latch.is_set():
            raise error.TestError('Never received callback from browser.')

        # Ensure chrome writes state to disk.
        self.logout()
        self.login()

        # Check mtime of Default/Cookies.  If changed, KABLOOEY.
        new_cookies_mtime = self.__get_cookies_mtime()

        if new_cookies_mtime and cookies_mtime != new_cookies_mtime:
            raise error.TestFail('Cookies in Default profile changed!')
