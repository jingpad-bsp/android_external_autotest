# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import tcpdump_analyzer
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server.cros.network import hostap_config
from autotest_lib.server.cros.network import wifi_cell_test_base


class network_WiFi_VisibleScan(wifi_cell_test_base.WiFiCellTestBase):
    """Test scanning behavior when no hidden SSIDs are configured."""

    version = 1

    # The number of bytes needed is hard to define, because the frame
    # contents are variable (e.g. radiotap header may contain
    # different fields, maybe SSID isn't the first tagged
    # parameter?). The value here is 2x the largest frame size
    # observed in a quick sample.
    TEST_SNAPLEN = 600
    BROADCAST_SSID = ''

    def parse_additional_arguments(self, commandline_args, additional_params):
        """
        Hook into super class to take control files parameters.

        @param commandline_args: dict of parsed parameters from the autotest.
        @param additional_params: list of HostapConfig objects.

        """
        self._ap_configs = additional_params


    def get_probe_ssids(self, pcap_result):
        """
        Parse a pcap, returning all the SSIDs that we requested in our
        802.11 probe request messages.

        @param pcap_result: RemoteCaptureResult tuple.
        @return: A frozenset of the unique SSIDs that were probed.

        """
        logging.info('Analyzing packet capture...')
        pcap_filter = ('wlan type mgt subtype probe-req and wlan addr2 %s'
                       % self.context.client.wifi_mac)
        frames = tcpdump_analyzer.get_frames(
                pcap_result.pcap_path,
                remote_host=self.context.router.host,
                pcap_filter=pcap_filter)

        return frozenset(
                [frame.probe_ssid for frame in frames
                 if frame.probe_ssid is not None])


    def run_once(self):
        """Test body."""
        ap_config = hostap_config.HostapConfig(channel=1)
        # Set up the router and associate the client with it.
        self.context.configure(ap_config)
        self.context.router.start_capture(
                ap_config.frequency,
                ht_type=ap_config.ht_packet_capture_mode,
                snaplen=self.TEST_SNAPLEN)
        assoc_params = xmlrpc_datatypes.AssociationParameters(
                ssid=self.context.router.get_ssid())
        self.context.assert_connect_wifi(assoc_params)
        results = self.context.router.stop_capture()
        if len(results) != 1:
            raise error.TestError('Expected to generate one packet '
                                  'capture but got %d instead.' %
                                  len(results))
        probe_ssids = self.get_probe_ssids(results[0])
        if len(probe_ssids) != 1:
            raise error.TestError('Expected exactly one SSID, but got %s' %
                                  probe_ssids)
        if probe_ssids - {self.BROADCAST_SSID}:
            raise error.TestError('Expected broadcast SSID, but got %s' %
                                  probe_ssids)
