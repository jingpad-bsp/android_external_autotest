# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server import site_linux_system
from autotest_lib.server.cros.network import hostap_config
from autotest_lib.server.cros.network import wifi_cell_test_base


class network_WiFi_VerifyRouter(wifi_cell_test_base.WiFiCellTestBase):
    """Test that a dual radio router can use both radios."""
    version = 1

    def _connect(self, wifi_params):
        assoc_result = xmlrpc_datatypes.deserialize(
                self.context.client.shill.connect_wifi(wifi_params))
        logging.info('Finished connection attempt to %s with times: '
                     'discovery=%.2f, association=%.2f, configuration=%.2f.',
                     wifi_params.ssid,
                     assoc_result.discovery_time,
                     assoc_result.association_time,
                     assoc_result.configuration_time)
        return assoc_result.success


    def _antenna_test(self, channel):
        """Test to verify each antenna is working on given band.

        Setup AP in each radio in given band, and run connection test with one
        antenna active at a time, to verify each antenna in each radio is
        working correctly for given band. Antenna can only be configured when
        the wireless interface is down.

        @param channel: int Wifi channel to conduct test on

        """
        # Connect to AP with only one antenna active at a time
        for bitmap in (3, 1, 2):
            self.context.router.deconfig()
            self.context.router.set_antenna_bitmap(bitmap, bitmap)
            # Setup two APs in the same band
            n_mode = hostap_config.HostapConfig.MODE_11N_MIXED
            ap_config = hostap_config.HostapConfig(channel=channel, mode=n_mode)
            self.context.configure(ap_config)
            self.context.configure(ap_config, multi_interface=True)
            # Added delay to allow APs to "stabilize" before connection attempt.
            # Connection will fail randomly with antenna bitmap of 2 and AP
            # configured with channel 136. Leave this hack here until we figure
            # out the root cause of the random connection failures.
            time.sleep(5.0)
            # Verify connectivity to both APs
            for instance in range(2):
                context_message = ('bitmap=%d, ap_instance=%d, channel=%d' %
                                   (bitmap, instance, channel))
                logging.info('Connecting to AP with settings %s.',
                             context_message)
                client_conf = xmlrpc_datatypes.AssociationParameters(
                        ssid=self.context.router.get_ssid(instance=instance))
                if self._connect(client_conf):
                    signal_level = self.context.client.wifi_signal_level
                    logging.info('Signal level for AP %d with bitmap %d is %d',
                                 instance, bitmap, signal_level)
                    self.write_perf_keyval(
                            {'signal_for_ap_%d_bm_%d_ch_%d' %
                                     (instance, bitmap, channel):
                             signal_level})
                else:
                    self.failures.append(context_message)


    def cleanup(self):
        """Clean up after the test is completed

        Perform additional cleanups after the test, the important thing is
        to restore default antennas bitmap.
        """
        self.context.router.deconfig()
        self.context.router.set_default_antenna_bitmap()
        super(network_WiFi_VerifyRouter, self).cleanup()


    def run_once(self):
        """Set up two APs connect to both and then exit."""
        self.context.router.require_capabilities(
                [site_linux_system.LinuxSystem.CAPABILITY_MULTI_AP_SAME_BAND])

        self.failures = []
        # Run antenna test for 2GHz band and 5GHz band
        self._antenna_test(6)
        self._antenna_test(136)
        if self.failures:
            all_failures = ', '.join(
                    ['(' + message + ')' for message in self.failures])
            raise error.TestFail('Failed to connect when %s.' % all_failures)
