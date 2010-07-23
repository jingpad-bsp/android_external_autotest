# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, time
from autotest_lib.client.bin import site_login, site_ui_test, site_utils
from autotest_lib.client.common_lib import error

class desktopui_ChromeFirstRender(site_ui_test.UITest):
    version = 1


    _LOGIN_SUCCESS_FILE = '/tmp/uptime-login-success'
    _FIRST_RENDER_FILE = '/tmp/uptime-chrome-first-render'

    def __parse_uptime(self, target_file):
        data = file(target_file).read()
        time = re.split(r' +', data.strip())[0]
        return float(time)


    def run_once(self):
        try:
            site_utils.poll_for_condition(
                lambda: os.access(self._LOGIN_SUCCESS_FILE, os.F_OK),
                site_login.TimeoutError('Timed out waiting for initial login'))
            site_utils.poll_for_condition(
                lambda: os.access(self._FIRST_RENDER_FILE, os.F_OK),
                site_login.TimeoutError('Timed out waiting for initial render'))

            start_time = self.__parse_uptime(self._LOGIN_SUCCESS_FILE)
            end_time = self.__parse_uptime(self._FIRST_RENDER_FILE)
            self.write_perf_keyval(
                { 'seconds_chrome_first_tab': end_time - start_time })
        except IOError, e:
            logging.debug(e)
            raise error.TestFail('Login information missing')
