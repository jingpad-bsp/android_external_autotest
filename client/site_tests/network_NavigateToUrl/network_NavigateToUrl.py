# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import time
import urllib

from autotest_lib.client.bin import utils
from autotest_lib.client.cros import cros_ui_test
from autotest_lib.client.cros import flimflam_test_path
import flimflam


class network_NavigateToUrl(cros_ui_test.UITest):
    version = 1

    DEFAULT_URL = 'http://www.msn.com'
    DEFAULT_EXPECT_TITLE = 'MSN.com'

    TIMEOUT = 20

    def initialize(self, device='ethernet', **params):
        # Modify the service order so NavigateToUrl
        # goes through the prioritiezed network interface.
        logging.debug('Disabling all devices but %s', device)

        super(network_NavigateToUrl, self).initialize(**params)
        self.shill_device_manager = flimflam.DeviceManager()
        self.shill_device_manager.ShutdownAllExcept(device)

        self._webdriver = self.pyauto.NewWebDriver()


    def cleanup(self):
        self.shill_device_manager.RestoreDevices()
        super(network_NavigateToUrl, self).cleanup()


    def start_authserver(self):
        # We want to be able to get to the real internet.
        pass


    def run_once(self, url=DEFAULT_URL, expect_title=DEFAULT_EXPECT_TITLE):
        # Assume the test is passing.  Set client_passed appropriately
        # when something fails.
        self.job.set_state('client_passed', None)
        self._webdriver.get(url)
        end_time = time.time() + self.TIMEOUT

        while time.time() < end_time:
            if self._webdriver.title == expect_title:
                logging.info('Successfully connected to %s', url)
                self.job.set_state('client_passed', True)
                break
        else:
            # We failed to load the page.
            logging.info('There was an error running navigate to URL.')
            self.job.set_state('client_passed', False)
