# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, time
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants, cros_logging, cros_ui
from autotest_lib.client.cros import cros_ui_test, login, httpd


class desktopui_FlashSanityCheck(cros_ui_test.UITest):
    version = 3

    def initialize(self):
        self._test_url = 'http://localhost:8000/index.html'
        self._testServer = httpd.HTTPListener(8000, docroot=self.srcdir)
        self._testServer.run()
        super(desktopui_FlashSanityCheck, self).initialize()


    def run_once(self, time_to_wait=25):
        self._log_reader = cros_logging.LogReader()
        self._log_reader.set_start_by_current()

        # Make sure that we don't have the initial browser window popping up in
        # the middle of the test.
        login.wait_for_initial_chrome_window()
        session = cros_ui.ChromeSession(args=self._test_url)
        # TODO(nirnimesh) use pyauto to accurately wait.
        time.sleep(time_to_wait)

        # Any better pattern matching?
        msg = ' Received crash notification for ' + constants.BROWSER
        if self._log_reader.can_find(msg):
            raise error.TestFail('Browser crashed during test.')


    def cleanup(self):
        self._testServer.stop()
        super(desktopui_FlashSanityCheck, self).cleanup()
