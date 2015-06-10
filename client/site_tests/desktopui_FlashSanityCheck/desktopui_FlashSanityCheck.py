# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import constants, cros_logging
from autotest_lib.client.cros import httpd


class desktopui_FlashSanityCheck(test.test):
    """Sanity test that ensures flash instance is launched when a swf is played.

    """
    version = 4

    _messages_log_reader = None
    _ui_log_reader = None
    _test_url = None
    _testServer = None

    def initialize(self):
        logging.info('initialize()')
        self._test_url = 'http://localhost:8000/index.html'
        self._testServer = httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()
        logging.info('initialize sleep')
        time.sleep(2)

    def cleanup(self):
        self._testServer.stop()

    def run_flash_sanity_test(self, browser, time_to_wait_secs):
        """Run the Flash sanity test.

        @param browser: The Browser object to run the test with.
        @param time_to_wait_secs: wait time for swf file to load.

        """
        logging.info('Sleeping 2 seconds.')
        time.sleep(2)
        logging.info('Getting tab from telemetry...')
        tab = browser.tabs[0]
        logging.info('Initializing logs.')
        self._messages_log_reader = cros_logging.LogReader()
        self._messages_log_reader.set_start_by_current()
        self._ui_log_reader = cros_logging.LogReader('/var/log/ui/ui.LATEST')
        self._ui_log_reader.set_start_by_current()
        logging.info('Done initializing logs.')

        # Ensure that the swf got pulled.
        latch = self._testServer.add_wait_url('/Trivial.swf')
        tab.Navigate(self._test_url)
        tab.WaitForDocumentReadyStateToBeComplete()
        logging.info('Waiting up to %ds for document.', time_to_wait_secs)
        latch.wait(time_to_wait_secs)

        logging.info('Waiting for Pepper process.')
        # Verify that we see a ppapi process and assume it is Flash.
        prc = utils.wait_for_value(
            lambda: (utils.get_process_list('chrome', '--type=ppapi')),
            timeout_sec=30)
        logging.info('ppapi process list at start: %s', ', '.join(prc))
        if not prc:
            raise error.TestFail('No Flash process found.')

        # Let Flash run for a little and see if it is still alive.
        logging.info('Running Flash content for a little while.')
        time.sleep(5)
        logging.info('Verifying Pepper process is still around.')
        prc = utils.wait_for_value(
            lambda: (utils.get_process_list('chrome', '--type=ppapi')),
            timeout_sec=3)
        # Notice that we are not checking for equality of prc on purpose.
        logging.info('PPapi process list found: %s', ', '.join(prc))
        # At a minimum Flash identifies itself during process start.
        msg = 'flash/platform/pepper/pep_'
        if not self._ui_log_reader.can_find(msg):
            raise error.TestFail('Did not find any Pepper Flash output.')

        # Any better pattern matching?
        msg = ' Received crash notification for ' + constants.BROWSER
        if self._messages_log_reader.can_find(msg):
            raise error.TestFail('Browser crashed during test.')

        if not prc:
            raise error.TestFail('Pepper process disappeared during test.')

    def run_once(self, time_to_wait_secs=60):
        with chrome.Chrome() as cr:
            self.run_flash_sanity_test(cr.browser, time_to_wait_secs)
