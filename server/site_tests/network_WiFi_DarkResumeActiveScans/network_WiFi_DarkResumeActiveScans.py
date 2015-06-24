# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import tcpdump_analyzer
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server import site_linux_system
from autotest_lib.server.cros import dark_resume_utils
from autotest_lib.server.cros.network import hostap_config
from autotest_lib.server.cros.network import wifi_cell_test_base
from autotest_lib.server.cros.network import wifi_client

class network_WiFi_DarkResumeActiveScans(wifi_cell_test_base.WiFiCellTestBase):
    """
    Test that no active scans are launched when the system wakes on dark resumes
    triggered by RTC timers and wake on pattern.
    """

    version = 1

    def initialize(self, host):
        super(network_WiFi_DarkResumeActiveScans, self).initialize(host)
        """Set up for dark resume."""
        self._dr_utils = dark_resume_utils.DarkResumeUtils(host)


    def stop_capture_and_check_for_probe_requests(self, mac):
        """
        Stop packet capture and check that no probe requests launched by the DUT
        with MAC address |mac| are found in the packet capture.  Fails test if
        any probe request frames are found.

        @param mac: MAC address of the DUT.
        """
        logging.info('Stopping packet capture')
        results = self.context.router.stop_capture()
        if len(results) != 1:
            raise error.TestError('Expected to generate one packet '
                                  'capture but got %d captures instead.' %
                                  len(results))

        logging.info('Analyzing packet capture...')
        probe_req_pcap_filter = '%s and wlan.sa==%s' % (
                tcpdump_analyzer.WLAN_PROBE_REQ_FILTER, mac)
        # Get all the frames in chronological order.
        frames = tcpdump_analyzer.get_frames(
                results[0].local_pcap_path,
                probe_req_pcap_filter)
        if len(frames) > 0:
            raise error.TestFail('Packet capture contained probe requests!')

        logging.info('Packet capture contained no probe requests')


    def run_once(self):
        """Body of the test."""
        self.context.router.require_capabilities(
                [site_linux_system.LinuxSystem.CAPABILITY_MULTI_AP_SAME_BAND])

        ap_config = hostap_config.HostapConfig(channel=1)
        self.context.configure(ap_config)
        assoc_params = xmlrpc_datatypes.AssociationParameters(
                ssid=self.context.router.get_ssid())
        self.context.assert_connect_wifi(assoc_params)
        self.context.assert_ping_from_dut()

        client = self.context.client
        router = self.context.router
        dut_mac = client.wifi_mac
        dut_ip = client.wifi_ip
        prev_num_dark_resumes = 0

        logging.info('DUT WiFi MAC = %s, IPv4 = %s', dut_mac, dut_ip)
        logging.info('Router WiFi IPv4 = %s', router.wifi_ip)

        # Trigger a wake on packet dark resume, and make sure that no probe
        # requests were launched during this dark resume.
        with client.wake_on_wifi_features(wifi_client.WAKE_ON_WIFI_PACKET):
            logging.info('Set up WoWLAN')

            # Wake on packets from the router.
            client.add_wake_packet_source(self.context.router.wifi_ip)

            with self._dr_utils.suspend():
                time.sleep(wifi_client.SUSPEND_WAIT_TIME_SECONDS)

                # Start capture after suspend concludes in case probe requests
                # are launched on the way to suspend.
                self.context.router.start_capture(
                        ap_config.frequency,
                        ht_type=ap_config.ht_packet_capture_mode)

                # Send the DUT a packet from the router to wake it up.
                router.send_magic_packet(dut_ip, dut_mac)

                # Wait for the DUT to wake up in dark resume and suspend again.
                time.sleep(wifi_client.RECEIVE_PACKET_WAIT_TIME_SECONDS +
                           wifi_client.DARK_RESUME_WAIT_TIME_SECONDS)

                # Check for packet capture before waking the DUT with
                # |count_dark_resumes| because probe requests might be launched
                # during the wake.
                self.stop_capture_and_check_for_probe_requests(mac=dut_mac)

                prev_num_dark_resumes = self._dr_utils.count_dark_resumes()
                if prev_num_dark_resumes < 1:
                    raise error.TestFail('Client failed to wake on packet.')
                logging.info('Client woke up on packet successfully.')

        # Trigger a wake to scan RTC timer dark resume, and make sure that no
        # probe requests were launched during this dark resume.
        with contextlib.nested(
                client.wake_on_wifi_features(wifi_client.WAKE_ON_WIFI_SSID),
                client.wake_to_scan_period_seconds(
                        wifi_client.WAKE_TO_SCAN_PERIOD_SECONDS),
                client.force_wake_to_scan_timer(True)):

            # Bring the AP down so the DUT suspends disconnected.
            router.deconfig_aps()
            time.sleep(wifi_client.DISCONNECT_WAIT_TIME_SECONDS)

            with self._dr_utils.suspend():
                time.sleep(wifi_client.SUSPEND_WAIT_TIME_SECONDS)

                # Start capture after suspend concludes in case probe requests
                # are launched on the way to suspend.
                self.context.router.start_capture(
                        ap_config.frequency,
                        ht_type=ap_config.ht_packet_capture_mode)

                # Wait for the DUT to wake to scan and suspend again.
                time.sleep(wifi_client.WAKE_TO_SCAN_PERIOD_SECONDS +
                           wifi_client.DARK_RESUME_WAIT_TIME_SECONDS)

                # Check for packet capture before waking the DUT with
                # |count_dark_resumes| because probe requests might be launched
                # during the wake.
                self.stop_capture_and_check_for_probe_requests(mac=dut_mac)

                if (self._dr_utils.count_dark_resumes() -
                    prev_num_dark_resumes) < 1:
                    raise error.TestFail('Client failed to wake up to scan.')
                logging.info('Client woke up to scan successfully.')


    def cleanup(self):
        self._dr_utils.teardown()
        # Make sure we clean up everything
        super(network_WiFi_DarkResumeActiveScans, self).cleanup()
