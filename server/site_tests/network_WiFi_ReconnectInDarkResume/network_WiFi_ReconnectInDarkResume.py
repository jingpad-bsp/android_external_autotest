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

class network_WiFi_ReconnectInDarkResume(wifi_cell_test_base.WiFiCellTestBase):
    """Test that known WiFi access points wake up the system."""

    version = 1

    def initialize(self, host):
        """Set up for dark resume."""
        self._dr_utils = dark_resume_utils.DarkResumeUtils(host)


    def check_connected_on_last_resume(self):
        """Checks whether the DUT was connected on its last resume.

        Checks that the DUT was connected after waking from suspend by parsing
        the last instance shill log message that reports shill's connection
        status on resume. Fails the test if this log message reports that
        the DUT woke up disconnected.

        """
        # The shill log message from the function OnAfterResume is called
        # as soon as shill resumes from suspend, and will report whether or not
        # shill is connected. The log message will take one of the following
        # two forms:
        #
        #       [...] (wake_on_wifi) OnAfterResume: connected
        #       [...] (wake_on_wifi) OnAfterResume: not connected
        #
        # By checking if the last instance of this message contains the
        # substring "not connected", we can determine whether or not shill was
        # connected on its last resume.
        connection_status_msg_substr = 'OnAfterResume'
        not_connected_substr = 'not connected'

        cmd = ('cat /var/log/net.log | grep %s | tail -1' %
               connection_status_msg_substr)
        cmdresult = self.context.client.host.run(cmd).stdout
        if not_connected_substr in cmdresult:
            raise error.TestFail(
                    'Client was not connected upon waking from suspend.')
        logging.info('Client was connected upon waking from suspend.')


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

            with self._dr_utils.suspend():
                # Wait for suspend actions to finish.
                time.sleep(wifi_client.SUSPEND_WAIT_TIME_SECONDS)

                # Bring the AP down so that DUT is disconnected.
                router.deconfig_aps()

                # Wait for the DUT to wake on disconnect in dark resume, then
                # suspend again.
                time.sleep(wifi_client.DARK_RESUME_WAIT_TIME_SECONDS)

                # Bring the AP back up to wake up the DUT.
                logging.info('Bringing AP back online.')
                self.context.configure(hostap_config.HostapConfig(
                        ssid=ap_ssid, channel=1))

                # Wait long enough for the NIC on the DUT to perform a net
                # detect scan, discover the AP with the white-listed SSID, wake
                # up in dark resume, connect, then suspend again.
                time.sleep(wifi_client.NET_DETECT_SCAN_WAIT_TIME_SECONDS +
                           wifi_client.DARK_RESUME_WAIT_TIME_SECONDS)

            self.check_connected_on_last_resume()


    def cleanup(self):
        self._dr_utils.teardown()
        # Make sure we clean up everything
        super(network_WiFi_ReconnectInDarkResume, self).cleanup()
