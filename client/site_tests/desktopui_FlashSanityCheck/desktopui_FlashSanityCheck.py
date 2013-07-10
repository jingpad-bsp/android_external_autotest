# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time

from telemetry.core.chrome import cros_interface

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants, cros_logging
from autotest_lib.client.cros import httpd
from autotest_lib.client.common_lib.cros import chrome


FLASH_PROCESS_NAME = 'chrome/chrome --type=ppapi'


class desktopui_FlashSanityCheck(test.test):
    version = 4


    def initialize(self):
        self._test_url = 'http://localhost:8000/index.html'
        self._testServer = httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()


    def cleanup(self):
        self._testServer.stop()


    def run_flash_sanity_test(self, browser, time_to_wait_secs):
        """Run the Flash sanity test.

        @param browser: The Browser object to run the test with.
        @param time_to_wait_secs: wait time for swf file to load.

        """
        tab = browser.tabs[0]
        self._log_reader = cros_logging.LogReader()
        self._log_reader.set_start_by_current()

        # Ensure that the swf got pulled
        latch = self._testServer.add_wait_url('/Trivial.swf')
        tab.Navigate(self._test_url)
        latch.wait(time_to_wait_secs)

        prc = [proc for proc in cros_interface.CrOSInterface().ListProcesses()
                if FLASH_PROCESS_NAME in proc[1]]
        if not prc:
            raise error.TestFail('No Flash process found.')

        # Any better pattern matching?
        msg = ' Received crash notification for ' + constants.BROWSER
        if self._log_reader.can_find(msg):
            raise error.TestFail('Browser crashed during test.')


    def run_once(self, time_to_wait_secs=25):
        with chrome.login() as browser:
            self.run_flash_sanity_test(browser, time_to_wait_secs)
