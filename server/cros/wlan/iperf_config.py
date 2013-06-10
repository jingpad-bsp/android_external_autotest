# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error


class IperfConfig(object):
    """Parameters for iperf test configuration."""

    IPERF_PORT = 12866
    TEST_TIME_SECONDS = 10
    UDP_BANDWIDTH_MBPS = '150M'
    TCP_WINDOW_SIZE_KB = '512K'
    BUFSIZE_BYTES = 1500
    PROTOCOL_UDP = 'udp'
    PROTOCOL_TCP = 'tcp'


    @property
    def protocol(self):
        """@return test traffic protocol."""
        return self._protocol


    @property
    def is_downstream(self):
        """@return test traffic direction."""
        return self._is_downstream


    @property
    def test_time(self):
        """@return test run time."""
        return self._test_time


    def get_sink_cmd(self, cmd):
        """Constructs command to start iperf server.

        Run iperf server in background so it's non-blocking.
        Caller can terminate the server process through pkill.

        @param cmd: a string, path to iperf binary on server.
        @return a string, iperf command to run on server.
        """
        return '%s -s %s &> /dev/null' % (cmd, self._iperf_common_args)


    def get_source_cmd(self, cmd, server_ip):
        """Constructs command to start iperf client.

        @param cmd: a string, path to iperf binary on client.
        @param server_ip: a string, IP address of server to connect to.
        @return a string, iperf command to run on client.
        """
        return '%s -c %s%s' % (cmd, server_ip, self._iperf_client_args)


    def _build_iperf_common_args(self):
        """@return iperf command-line args shared between server and client."""
        iperf_args = ''
        if self._protocol == self.PROTOCOL_UDP:
            iperf_args += ' -u'

        # '-w' flag is only relevant for TCP test.
        if self._protocol == self.PROTOCOL_TCP:
            iperf_args += ' -w %s' % self._tcp_wnd_size

        # Set buffer size in bytes
        iperf_args += ' -l %s' % self._bufsize

        # Set iperf port
        iperf_args += ' -p %s' % self.IPERF_PORT
        return iperf_args


    def _build_iperf_client_args(self):
        """@return iperf client command-line args."""
        iperf_client_args = (self._iperf_common_args +
                             ' -f m -t %s' % self._test_time)
        if self._protocol == self.PROTOCOL_UDP:
            iperf_client_args += ' -b %s' % self._udp_bw

        return iperf_client_args


    def __init__(self, protocol=None, is_downstream=None, test_time=None,
                 bufsize=None, tcp_wnd_size=None, udp_bw=None):
        """Initialize iperf configuration parameters.

        @param protocol: a string, test traffic protocol.
        @param is_downstream: a boolean, True == run downstream test.
        @param test_time: an integer, number of seconds to run iperf.
        @param bufsize: an integer, length of buffer in bytes.
        @param tcp_wnd_size: a string, iperf TCP window size.
        @param udp_bw: a string, iperf UDP bandwidth.

        @raises TestFail if a param is invalid.
        """
        # Valid iperf test traffic protocol is UDP or TCP.
        self._protocol = self.PROTOCOL_UDP
        if protocol is not None:
            if protocol not in [self.PROTOCOL_UDP, self.PROTOCOL_TCP]:
                err = ('Invalid protocol %r. Valid values are %r and %r' %
                       (protocol, self.PROTOCOL_UDP, self.PROTOCOL_TCP))
                raise error.TestFail(err)

            self._protocol = protocol
        logging.info('Iperf protocol = %s.', self._protocol)

        # Valid iperf test traffic direction is either downstream or upstream.
        # Although iperf also supports bi-directional traffic, we do not use it.
        self._is_downstream = True
        if is_downstream is not None:
            self._is_downstream = is_downstream
        logging.info('Iperf traffic is_downstream = %r.', self._is_downstream)

        # Test time is a positive integer with no absolute bounds.
        # Use TEST_TIME_SECONDS as a lower bound to meet usual dev need.
        self._test_time = self.TEST_TIME_SECONDS
        if test_time is not None:
            self._test_time = int(test_time)
        logging.info('Iperf test time = %d.', self._test_time)

        # Length of buffer to read or write should be a positive integer.
        self._bufsize = self.BUFSIZE_BYTES
        if bufsize is not None:
            self._bufsize = int(bufsize)
        logging.info('Iperf buffer len = %d.', self._bufsize)

        # Parse protocol-specific flags.
        self._tcp_wnd_size = self.TCP_WINDOW_SIZE_KB
        if self._protocol == self.PROTOCOL_TCP:
            if tcp_wnd_size is not None:
                self._tcp_wnd_size = tcp_wnd_size
            logging.info('Iperf TCP window size = %s.', self._tcp_wnd_size)

        self._udp_bw = self.UDP_BANDWIDTH_MBPS
        if self._protocol == self.PROTOCOL_UDP:
            if udp_bw is not None:
                self._udp_bw = udp_bw
            logging.info('Iperf UDP bandwidth = %s.', self._udp_bw)

        self._iperf_common_args = self._build_iperf_common_args()
        self._iperf_client_args = self._build_iperf_client_args()


    def __str__(self):
        """@return class name and iperf config params."""
        return (('%s(protocol = %s, is_downstream = %s, test_time = %d,'
                 ' bufsize = %s, tcp_wnd_size = %s, udp_bw = %s)') %
                (self.__class__.__name__, self._protocol, self._is_downstream,
                 self._test_time, self._bufsize, self._tcp_wnd_size,
                 self._udp_bw))
