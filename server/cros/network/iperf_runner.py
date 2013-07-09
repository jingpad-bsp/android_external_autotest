# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server import site_linux_server
from autotest_lib.server.cros import remote_command
from autotest_lib.server.cros.network import wifi_client


class IperfRunner(object):
    """Helper object to manage iperf test."""


    WAIT_TIME_IN_SECONDS = 3


    def __init__(self, dut, ap):
        """Initialize.

        @param dut: a WiFiClient object, representing DUT.
        @param ap: a LinuxCrosRouter object, representing AP.
        """
        self._dut = dut
        self._ap = ap


    def _parse_tcp_results(self, lines):
        """Parses TCP iperf test result.

        ------------------------------------------------------------
        Client connecting to localhost, TCP port 5001
        TCP window size: 49.4 KByte (default)
        ------------------------------------------------------------
        [  3] local 127.0.0.1 port 57936 connected with 127.0.0.1 port 5001
        [ ID] Interval       Transfer     Bandwidth
        [  3]  0.0-10.0 sec  2.09 GBytes  1.79 Gbits/sec

        @returns a Python dictionary containing throughput. Or None.
        """
        result = None
        tcp_tokens = lines[6].split()
        if len(tcp_tokens) >= 6 and tcp_tokens[-1].endswith('bits/sec'):
            result = {'throughput': float(tcp_tokens[-2])}
        return result


    def _parse_udp_results(self, lines):
        """Parses UDP iperf test result.

        ------------------------------------------------------------
        Client connecting to localhost, UDP port 5001
        Sending 1470 byte datagrams
        UDP buffer size:   108 KByte (default)
        ------------------------------------------------------------
        [  3] local 127.0.0.1 port 54244 connected with 127.0.0.1 port 5001
        [ ID] Interval       Transfer     Bandwidth
        [  3]  0.0-10.0 sec  1.25 MBytes  1.05 Mbits/sec
        [  3] Sent 893 datagrams
        [  3] Server Report:
        [ ID] Interval       Transfer     Bandwidth       Jitter   Lost/Total Datagrams
        [  3]  0.0-10.0 sec  1.25 MBytes  1.05 Mbits/sec  0.032 ms    1/  894 (0.11%)
        [  3]  0.0-15.0 sec  14060 datagrams received out-of-order

        @returns a Python dictionary containing throughput, jitter and
                 number of errors. Or None.
        """
        result = None
        # Search for the last row containing the word 'Bytes'
        mb_row = [row for row,data in enumerate(lines)
                  if 'Bytes' in data][-1]
        udp_tokens = lines[mb_row].replace('/', ' ').split()
        # Find the column ending with '...Bytes'
        mb_col = [col for col,data in enumerate(udp_tokens)
                  if data.endswith('Bytes')]
        if len(mb_col) > 0 and len(udp_tokens) >= mb_col[0] + 9:
            # Make a sublist starting after the column named 'MBytes'
            stat_tokens = udp_tokens[mb_col[0]+1:]
            result = {'throughput': float(stat_tokens[0]),
                      'jitter': float(stat_tokens[3]),
                      'lost': float(stat_tokens[7].strip('()%'))}
        return result


    def run(self, config):
        """Executes iperf w/ user-specified command-line options

        @param config an IperfConfig object, params to run iperf test.
        @returns a Python dictionary, iperf test measurements.
        """
        results = None
        if config.is_downstream:
            source_host = self._ap.server
            sink_host = self._dut.client
            source_cmd = config.get_source_cmd(self._ap.cmd_iperf,
                                               self._dut.wifi_ip)
            sink_cmd = config.get_sink_cmd(self._dut.command_iperf)
        else:
            source_host = self._dut.client
            sink_host = self._ap.server
            source_cmd = config.get_source_cmd(self._dut.command_iperf,
                                               self._ap.wifi_ip)
            sink_cmd = config.get_sink_cmd(self._ap.cmd_iperf)

        logging.info('\niperf_source_cmd = %s\niperf_sink_cmd = %s\n',
                     source_cmd, sink_cmd)
        try:
            # Open firewall on DUT
            self._dut.firewall_open(config.protocol, self._ap.wifi_ip)
            # Firewalls are opened on Stumpy at boot time

            iperf_thread = remote_command.Command(sink_host, sink_cmd)
            # NB: block to allow server time to startup
            time.sleep(self.WAIT_TIME_IN_SECONDS)

            # Run iperf command and receive command results
            t0 = time.time()
            timeout = int(config.test_time) + self.WAIT_TIME_IN_SECONDS
            results = source_host.run(source_cmd, timeout=timeout)
            actual_time = time.time() - t0
            logging.info('actual_time: %f', actual_time)

            iperf_thread.join()
        finally:
            # Close up DUT firewall
            self._dut.firewall_cleanup()

        logging.info(results)
        lines = results.stdout.splitlines()
        # Each test type has a different form of output
        if config.protocol == config.PROTOCOL_TCP:
            return self._parse_tcp_results(lines)
        elif config.protocol == config.PROTOCOL_UDP:
            return self._parse_udp_results(lines)
