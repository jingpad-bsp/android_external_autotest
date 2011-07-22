# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, re
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import pyauto_test

class desktopui_PyAutoChromeFirstRender(pyauto_test.PyAutoTest):
    version = 1

    _LOGIN_SUCCESS_FILE = '/tmp/uptime-login-success'
    _FIRST_RENDER_FILE = '/tmp/uptime-chrome-first-render'

    def __parse_uptime(self, target_file):
        data = file(target_file).read()
        time = re.split(r' +', data.strip())[0]
        return float(time)

    def run_once(self):
        # Since we are subclassed from the pyauto dep we are already logged in
        # and the new tab page should be rendered.

        if not os.path.exists(self._LOGIN_SUCCESS_FILE):
            raise error.TestError('The file %s does not exist'
                                  % self._LOGIN_SUCCESS_FILE)

        if not os.path.exists(self._FIRST_RENDER_FILE):
            raise error.TestError('The file %s does not exist'
                                  % self._FIRST_RENDER_FILE)
        start_time = self.__parse_uptime(self._LOGIN_SUCCESS_FILE)
        end_time = self.__parse_uptime(self._FIRST_RENDER_FILE)
        self.write_perf_keyval(
            { 'seconds_chrome_first_tab': end_time - start_time })
