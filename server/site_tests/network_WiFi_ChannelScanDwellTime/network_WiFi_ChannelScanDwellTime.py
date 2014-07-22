# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import random
import string
import time

from autotest_lib.server.cros.network import frame_sender
from autotest_lib.server import site_linux_system
from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.network import wifi_cell_test_base


class network_WiFi_ChannelScanDwellTime(wifi_cell_test_base.WiFiCellTestBase):
    """Test for determine channel scan dwell time."""
    version = 1

    KNOWN_TEST_PREFIX = 'network_WiFi'
    SUFFIX_LETTERS = string.ascii_lowercase + string.digits
    DELAY_INTERVAL_MILLISECONDS = 1
    SCAN_RETRY_TIMEOUT_SECONDS = 10
    NUM_BSS = 1024
    MISSING_BEACON_THRESHOLD = 2

    def _build_ssid_prefix(self):
        """Build ssid prefix."""
        unique_salt = ''.join([random.choice(self.SUFFIX_LETTERS)
                               for x in range(5)])
        prefix = self.__class__.__name__[len(self.KNOWN_TEST_PREFIX):]
        prefix = prefix.lstrip('_')
        prefix += '_' + unique_salt + '_'
        return prefix[-23:]


    def _get_dwell_time(self, bss_list):
        """Parse scan result to get dwell time.

        Calculate dwell time based on the SSIDs in the scan result.

        @param bss_list: List of BSSs

        @return int dwell time in ms.
        """
        # Get ssid indices from the scan result.
        # Expected SSID format: [testName]_[salt]_[index]
        ssid_index = []
        for bss in bss_list:
            ssid = int(bss.ssid.split('_')[-1], 16)
            ssid_index.append(ssid)
        # Calculate dwell time based on the start ssid index and end ssid index.
        ssid_index.sort()
        index_diff = ssid_index[-1] - ssid_index[0]
        dwell_time = index_diff * self.DELAY_INTERVAL_MILLISECONDS
        # Check if number of missed beacon frames exceed the test threshold.
        missed_beacons = index_diff - (len(ssid_index) - 1)
        if missed_beacons > self.MISSING_BEACON_THRESHOLD:
            logging.info('Missed %d beacon frames, SSID Index: %r',
                         missed_beacons, ssid_index)
            raise error.TestFail('DUT missed more than %d beacon frames' %
                                 missed_beacons)
        return dwell_time


    def _channel_dwell_time_test(self, single_channel):
        """Perform test to determine channel dwell time.

        This function invoke FrameSender to continuously send beacon frames
        for specific number of BSSs with specific delay, the SSIDs of the
        BSS are in hex numerical order. And at the same time, perform wifi scan
        on the DUT. The index in the SSIDs of the scan result will be used to
        interpret the relative start time and end time of the channel scan.

        @param single_channel: bool perform single channel scan if true.

        @return int dwell time in ms.

        """
        dwell_time = 0
        ssid_prefix = self._build_ssid_prefix()
        with frame_sender.FrameSender(self.context.router, 'beacon', 1,
                                      ssid_prefix=ssid_prefix,
                                      num_bss = self.NUM_BSS,
                                      frame_count=0,
                                      delay=self.DELAY_INTERVAL_MILLISECONDS):
            if single_channel:
                frequencies = [2412]
            else:
                frequencies = []
            # Perform scan
            start_time = time.time()
            while time.time() - start_time < self.SCAN_RETRY_TIMEOUT_SECONDS:
                bss_list = self.context.client.iw_runner.scan(
                        self.context.client.wifi_if, frequencies=frequencies)

                if bss_list is not None:
                    break

                time.sleep(0.5)
            else:
                raise error.TestFail('Unable to trigger scan on client.')
            if not bss_list:
                raise error.TestFail('Failed to find any BSS')
            # Filter scan result based on ssid prefix to remove any cached
            # BSSs from previous run.
            result_list = [bss for bss in bss_list if
                           bss.ssid.startswith(ssid_prefix)]
            if result_list is None:
                raise error.TestFail('Failed to find any BSS for this test')
            dwell_time = self._get_dwell_time(result_list)
        return dwell_time


    def run_once(self):
        self.context.router.require_capabilities(
                  [site_linux_system.LinuxSystem.
                          CAPABILITY_SEND_MANAGEMENT_FRAME])
        # Get channel dwell time for single-channel scan
        dwell_time = self._channel_dwell_time_test(True)
        logging.info('Channel dwell time for single-channel scan: %d ms',
                     dwell_time)
        self.write_perf_keyval({'dwell_time_single_channel_scan': dwell_time})
