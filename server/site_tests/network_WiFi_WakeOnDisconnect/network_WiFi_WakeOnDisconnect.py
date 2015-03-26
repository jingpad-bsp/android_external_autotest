# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.client.common_lib import error
from autotest_lib.server.cros import dark_resume_utils
from autotest_lib.server.cros.network import hostap_config
from autotest_lib.server.cros.network import wifi_cell_test_base
from autotest_lib.server.cros.network import wifi_client

class network_WiFi_WakeOnDisconnect(wifi_cell_test_base.WiFiCellTestBase):
    """Test that WiFi disconnect wakes up the system."""

    version = 1

    def initialize(self, host):
        """Set up for dark resume."""
        self._dr_utils = dark_resume_utils.DarkResumeUtils(host)


    def run_once(self):
        """Body of the test."""
        self.context.configure(hostap_config.HostapConfig(channel=1))
        assoc_params = xmlrpc_datatypes.AssociationParameters(
                ssid=self.context.router.get_ssid())
        self.context.assert_connect_wifi(assoc_params)

        client = self.context.client
        router = self.context.router

        # ask shill to set up wake-on-ssid
        with client.wake_on_wifi_features(wifi_client.WAKE_ON_WIFI_SSID):
            logging.info('Set up WoWLAN')

            with self._dr_utils.suspend():
                time.sleep(wifi_client.SUSPEND_WAIT_TIME_SECONDS)

                # Kick over the router to trigger wake on disconnect.
                router.deconfig_aps(silent=True)

                # Wait for the DUT to wake up in dark resume and suspend again.
                time.sleep(wifi_client.DARK_RESUME_WAIT_TIME_SECONDS)

                # Ensure that wake on packet did not trigger a full wake.
                if client.host.wait_up(
                        timeout=wifi_client.WAIT_UP_TIMEOUT_SECONDS):
                    raise error.TestFail('Client woke up fully.')

                if self._dr_utils.count_dark_resumes() < 1:
                    raise error.TestFail('Client failed to wake up.')

                logging.info('Client woke up successfully.')


    def cleanup(self):
        self._dr_utils.teardown()
        # Make sure we clean up everything
        super(network_WiFi_WakeOnDisconnect, self).cleanup()
