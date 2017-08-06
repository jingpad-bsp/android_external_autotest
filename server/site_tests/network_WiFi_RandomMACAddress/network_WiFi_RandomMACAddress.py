# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import tcpdump_analyzer
from autotest_lib.server import site_linux_system
from autotest_lib.server.cros.network import hostap_config
from autotest_lib.server.cros.network import wifi_cell_test_base

class network_WiFi_RandomMACAddress(wifi_cell_test_base.WiFiCellTestBase):
    """
    Test that the MAC address is randomized during scans when we
    are not connected to an AP already.
    """

    version = 1

    # Approximate number of seconds to perform a full scan.
    REQUEST_SCAN_DELAY = 5

    def stop_capture_and_check_for_probe_requests(self, mac, ssid):
        """
        Stop packet capture and check that probe requests launched by the DUT
        have different MAC addresses than the hardware MAC address.

        @param mac: MAC address of the DUT.
        @param ssid: SSID of the AP.
        """
        logging.info('Stopping packet capture')
        results = self.context.capture_host.stop_capture()
        if len(results) != 1:
            raise error.TestError('Expected to generate one packet '
                                  'capture but got %d captures instead.',
                                  len(results))

        logging.info('Analyzing packet capture...')
        # Get all the frames in chronological order.
        frames = tcpdump_analyzer.get_frames(
                results[0].local_pcap_path,
                tcpdump_analyzer.WLAN_PROBE_REQ_ACCEPTOR,
                bad_fcs='include')

        if not frames:
            raise error.TestFail('No probe requests were found!')
        elif any((frame.ssid == ssid or frame.ssid == '') and
                  frame.source_addr == mac
                 for frame in frames):
            raise error.TestFail('Found probe requests with hardware MAC!')


    def run_once(self):
        """Body of the test."""
        self.context.router.require_capabilities(
                [site_linux_system.LinuxSystem.CAPABILITY_MULTI_AP_SAME_BAND])

        ap_config = hostap_config.HostapConfig(channel=1)
        self.context.configure(ap_config)

        client = self.context.client
        router = self.context.router
        dut_hw_mac = client.wifi_mac
        router_ssid = router.get_ssid()

        # Enable MAC address randomization in shill.
        with client.mac_address_randomization(True):
            self.context.capture_host.start_capture(
                    ap_config.frequency,
                    ht_type=ap_config.ht_packet_capture_mode)

            for i in range(5):
                # Request scan through shill rather than iw because iw won't
                # set the random MAC flag in the scan request netlink packet.
                client.shill.request_scan()
                time.sleep(self.REQUEST_SCAN_DELAY)

            self.stop_capture_and_check_for_probe_requests(mac=dut_hw_mac,
                                                           ssid=router_ssid)
