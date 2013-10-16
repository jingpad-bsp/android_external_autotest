# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import datetime
import logging
import re

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server.cros.network import hostap_config
from autotest_lib.server.cros.network import iw_runner
from autotest_lib.server.cros.network import netperf_runner
from autotest_lib.server.cros.network import wifi_cell_test_base


FrameLine = collections.namedtuple('FrameLine', ['time_delta_seconds',
                                                 'bit_rate',
                                                 'mcs_index'])


class network_WiFi_RateControl(wifi_cell_test_base.WiFiCellTestBase):
    """
    Test maximal achievable bandwidth on several channels per band.

    Conducts a performance test for a set of specified router configurations
    and reports results as keyval pairs.

    """

    version = 1

    # We only care about the encoding/MCS index of the frames, not the
    # contents.  Large snaplens fill up /tmp/ and make shuffling the bits
    # around take longer.  However, we might be interested in the contents of
    # the frames in the association process, and packets I've seen with HT IEs
    # seem to come in around 300 bytes.
    TEST_SNAPLEN = 400


    def parse_additional_arguments(self, commandline_args, additional_params):
        """
        Hook into super class to take control files parameters.

        @param commandline_args: dict of parsed parameters from the autotest.
        @param additional_params: list of HostapConfig objects.

        """
        self._ap_configs = additional_params


    def check_bitrates_in_capture(self, pcap_result, client_ip, frequency):
        """
        Check that frames in a packet capture have expected MCS indices.

        @param pcap_result: RemoteCaptureResult tuple.
        @param client_ip: string IP address of the client device in the packet
                capture.
        @param frequency: int frequency of packet capture in Mhz.

        """
        logging.info('Analyzing packet capture...')
        pcap_filter = 'udp and ip src host %s' % client_ip
        result = self.context.router.host.run(
                'tcpdump -ttttt -r %s "%s"' % (pcap_result.pcap_path,
                                               pcap_filter))
        frames = []
        # Right now we only care about the MCS index, but one can imagine
        # checking properties of the distribution of MCS index frames across
        # time.  Support that by parsing as much useful information as possible.
        logging.info('Parsing frames')
        bad_lines = 0
        for frame in result.stdout.splitlines():
            match = re.search(r'^(?P<ts>\d{2}:\d{2}:\d{2}\.\d{6}) .+ '
                              r'(?P<rate>\d+.\d) Mb/s MCS (?P<mcs_index>\d+)',
                              frame)
            if not match:
                bad_lines += 1
                continue
            rel_time = datetime.datetime.strptime(match.group('ts'),
                                                  '%H:%M:%S.%f')
            diff_seconds = rel_time.time()
            rate = float(match.group('rate'))
            mcs_index = int(match.group('mcs_index'))
            frames.append(FrameLine(diff_seconds, rate, mcs_index))
        if bad_lines:
            logging.error('Failed to parse %d lines.', bad_lines)

        logging.info('Grouping frames by MCS index')
        counts = {}
        for frame in frames:
            counts[frame.mcs_index] = counts.get(frame.mcs_index, 0) + 1
        logging.info('Saw WiFi frames with MCS indices: %r', counts)

        # Figure out the highest MCS index supported by this hardware.
        # The device should sense that it is in a clean RF environment and use
        # the highest index to achieve maximal throughput.
        phys = iw_runner.IwRunner(self.context.client.host).list_phys()
        if len(phys) != 1:
            raise error.TestFail('Test expects a single PHY, but we got %d' %
                                 len(phys))

        phy = phys[0]
        bands = [band for band in phy.bands if frequency in band.frequencies]
        if len(bands) != 1:
            raise error.TestFail('Test expects a single possible band for a '
                                 'given frequency, but this device has %d '
                                 'such bands.' % len(bands))

        band = bands[0]
        max_possible_index = -1
        for index in band.mcs_indices:
            # 32 is a special low throughput, high resilience mode.  Ignore it.
            if index > max_possible_index and index != 32:
                max_possible_index = index

        # Now figure out the index which the device sent the most packets with.
        dominant_index = None
        num_packets_sent = -1
        for index, num_packets in counts.iteritems():
            if num_packets > num_packets_sent:
                dominant_index = index
                num_packets_sent = num_packets

        # We should see that the device sent more frames with the maximal index
        # than anything else.  This checks that the rate controller is fairly
        # aggressive and using all of the device's capabilities.
        if dominant_index != max_possible_index:
            raise error.TestFail('Failed to use best possible MCS '
                                 'index %d in a clean RF environment: %r' %
                                 (max_possible_index, counts))


    def run_once(self):
        """Test body."""
        caps = [hostap_config.HostapConfig.N_CAPABILITY_GREENFIELD,
                hostap_config.HostapConfig.N_CAPABILITY_HT40]
        mode_11n = hostap_config.HostapConfig.MODE_11N_PURE
        get_config = lambda channel: hostap_config.HostapConfig(
                channel=channel, mode=mode_11n, n_capabilities=caps)
        netperf_config = netperf_runner.NetperfConfig(
                netperf_runner.NetperfConfig.TEST_TYPE_UDP_STREAM)
        for i, ap_config in enumerate([get_config(1), get_config(157)]):
            # Set up the router and associate the client with it.
            self.context.configure(ap_config)
            self.context.router.start_capture(
                    ap_config.frequency,
                    ht_type=ap_config.ht_packet_capture_mode,
                    snaplen=self.TEST_SNAPLEN)
            assoc_params = xmlrpc_datatypes.AssociationParameters(
                    ssid=self.context.router.get_ssid())
            self.context.assert_connect_wifi(assoc_params)
            with netperf_runner.NetperfRunner(self.context.client,
                                              self.context.server,
                                              netperf_config) as runner:
                runner.run()
            results = self.context.router.stop_capture()
            if len(results) != 1:
                raise error.TestError('Expected to generate one packet '
                                      'capture but got %d instead.' %
                                      len(results))

            client_ip = self.context.client.wifi_ip
            self.check_bitrates_in_capture(results[0], client_ip,
                                           ap_config.frequency)
            # Clean up router and client state for the next run.
            self.context.client.shill.disconnect(self.context.router.get_ssid())
            self.context.router.deconfig()
