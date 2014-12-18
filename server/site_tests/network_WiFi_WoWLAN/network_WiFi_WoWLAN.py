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

SUSPEND_WAIT_TIME=10
RESUME_WAIT_TIME=10


class network_WiFi_WoWLAN(wifi_cell_test_base.WiFiCellTestBase):
    """Test that WiFi packets can wake up the system."""

    version = 1

    def initialize(self, host):
        """Set up for dark resume."""
        dark_resume_utils.dark_resume_setup(host)


    def run_once(self):
        """Body of the test."""
        self.context.configure(hostap_config.HostapConfig(channel=1))
        assoc_params = xmlrpc_datatypes.AssociationParameters(
                ssid=self.context.router.get_ssid())
        self.context.assert_connect_wifi(assoc_params)

        client = self.context.client
        router = self.context.router
        dut_mac = client.wifi_mac
        dut_ip = client.wifi_ip

        logging.info('DUT WiFi MAC = %s, IPv4 = %s', dut_mac, dut_ip)
        logging.info('Router WiFi IPv4 = %s', router.wifi_ip)

        # set up WoWLAN to wake on packets and register ip, then sleep
        with client.wake_on_wifi_features(wifi_client.WAKE_ON_WIFI_PACKET):
            client.add_wake_packet_source(router.wifi_ip)
            logging.info('Set up WoWLAN')

            client.do_suspend_bg(SUSPEND_WAIT_TIME + RESUME_WAIT_TIME + 10)
            time.sleep(SUSPEND_WAIT_TIME)

            router.send_magic_packet(dut_ip, dut_mac)

            # The DUT should wake up soon, but we'll give it a bit of a
            # grace period.
            if not client.host.wait_up(timeout=RESUME_WAIT_TIME):
                raise error.TestFail('Client failed to wake up.')

            logging.info('Client woke up successfully.')


    def cleanup(self):
        # make sure the DUT is up on the way out
        self.context.client.host.servo.ctrl_key()
        # clean up packet wake sources
        self.context.client.remove_all_wake_packet_sources()

        dark_resume_utils.dark_resume_teardown(self.context.client.host)
        # make sure we clean up everything
        super(network_WiFi_WoWLAN, self).cleanup()
