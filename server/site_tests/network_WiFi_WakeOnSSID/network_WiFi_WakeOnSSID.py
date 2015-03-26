# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import logging
import time

from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.client.common_lib import error
from autotest_lib.server.cros import dark_resume_utils
from autotest_lib.server.cros.network import hostap_config
from autotest_lib.server.cros.network import wifi_cell_test_base
from autotest_lib.server.cros.network import wifi_client

class network_WiFi_WakeOnSSID(wifi_cell_test_base.WiFiCellTestBase):
    """Test that known WiFi access points wake up the system."""

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
        ap_ssid = router.get_ssid()

        # Enable the wake on SSID feature in shill, and set the scan period.
        with contextlib.nested(
                client.wake_on_wifi_features(wifi_client.WAKE_ON_WIFI_SSID),
                client.net_detect_scan_period_seconds(
                        wifi_client.NET_DETECT_SCAN_WAIT_TIME_SECONDS)):
            logging.info('Set up WoWLAN')

            # Bring the AP down so the DUT suspends disconnected.
            router.deconfig_aps()

            with self._dr_utils.suspend():
                # Wait for suspend actions and first scan to finish.
                time.sleep(wifi_client.SUSPEND_WAIT_TIME_SECONDS +
                           wifi_client.NET_DETECT_SCAN_WAIT_TIME_SECONDS)

                # Bring the AP back up to wake up the DUT.
                logging.info('Bringing AP back online.')
                self.context.configure(hostap_config.HostapConfig(
                        ssid=ap_ssid, channel=1))

                # Wait long enough for the NIC on the DUT to perform a net
                # detect scan, discover the AP with the white-listed SSID, wake
                # up in dark resume, then suspend again.
                time.sleep(wifi_client.NET_DETECT_SCAN_WAIT_TIME_SECONDS +
                           wifi_client.DARK_RESUME_WAIT_TIME_SECONDS)

                # Ensure that net detect did not trigger a full wake.
                if client.host.wait_up(
                        timeout=wifi_client.WAIT_UP_TIMEOUT_SECONDS):
                    raise error.TestFail('Client woke up fully.')

                if self._dr_utils.count_dark_resumes() < 1:
                    raise error.TestFail('Client failed to wake up.')

                logging.info('Client woke up successfully.')


    def cleanup(self):
        self._dr_utils.teardown()
        # Make sure we clean up everything
        super(network_WiFi_WakeOnSSID, self).cleanup()
