# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time
import os.path

from autotest_lib.client.common_lib import error

class NetperfResult(object):
    """Encapsulates logic to parse and represent netperf results."""

    @staticmethod
    def from_netperf_results(test_type, results, duration_seconds):
        """Parse the text output of netperf and return a NetperfResult.

        @param test_type string one of NetperfConfig.TEST_TYPE_* below.
        @param results string raw results from netperf.
        @param duration_seconds float number of seconds the test ran for.
        @return NetperfResult result.

        """
        lines = results.splitlines()
        if test_type in NetperfConfig.TCP_STREAM_TESTS:
            """Parses the following (works for both TCP_STREAM, TCP_MAERTS and
            TCP_SENDFILE) and returns a singleton containing throughput.

            TCP STREAM TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET to \
            foo.bar.com (10.10.10.3) port 0 AF_INET
            Recv   Send    Send
            Socket Socket  Message  Elapsed
            Size   Size    Size     Time     Throughput
            bytes  bytes   bytes    secs.    10^6bits/sec

            87380  16384  16384    2.00      941.28
            """
            return NetperfResult(duration_seconds,
                                 throughput=float(lines[6].split()[4]))

        if test_type in NetperfConfig.UDP_STREAM_TESTS:
            """Parses the following and returns a tuple containing throughput
            and the number of errors.

            UDP UNIDIRECTIONAL SEND TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET \
            to foo.bar.com (10.10.10.3) port 0 AF_INET
            Socket  Message  Elapsed      Messages
            Size    Size     Time         Okay Errors   Throughput
            bytes   bytes    secs            #      #   10^6bits/sec

            129024   65507   2.00         3673      0     961.87
            131072           2.00         3673            961.87
            """
            udp_tokens = lines[5].split()
            return NetperfResult(duration_seconds,
                                 throughput=float(udp_tokens[5]),
                                 errors=float(udp_tokens[4]))

        if test_type in NetperfConfig.REQUEST_RESPONSE_TESTS:
            """Parses the following which works for both rr (TCP and UDP)
            and crr tests and returns a singleton containing transfer rate.

            TCP REQUEST/RESPONSE TEST from 0.0.0.0 (0.0.0.0) port 0 AF_INET \
            to foo.bar.com (10.10.10.3) port 0 AF_INET
            Local /Remote
            Socket Size   Request  Resp.   Elapsed  Trans.
            Send   Recv   Size     Size    Time     Rate
            bytes  Bytes  bytes    bytes   secs.    per sec

            16384  87380  1        1       2.00     14118.53
            16384  87380
            """
            return NetperfResult(duration_seconds,
                                 transaction_rate=float(lines[6].split()[5]))

        raise error.TestFail('Invalid netperf test type: %r.' % test_type)


    def __init__(self, duration_seconds, throughput=None,
                 errors=None, transaction_rate=None):
        """Construct a NetperfResult.

        @param duration_seconds float how long the test took.
        @param throughput float test throughput in Mbps.
        @param errors int number of UDP errors in test.
        @param transaction_rate float transactions per second.

        """
        self.duration_seconds = duration_seconds
        self.throughput = throughput
        self.errors = errors
        self.transaction_rate = transaction_rate
        logging.info('netperf duration: %f seconds', duration_seconds)
        if throughput is not None:
            logging.info('netperf throughput: %f Mbps', throughput)
        if errors is not None:
            logging.info('netperf errors: %f UDP errors', errors)
        if transaction_rate is not None:
            logging.info('netperf transaction_rate: %f transactions/sec',
                         transaction_rate)


    def __repr__(self):
        return ('%s(duration_seconds=%f, throughput=%r, '
                'errors=%r, transaction_rate=%r)' % (self.__class__.__name__,
                                                     self.duration_seconds,
                                                     self.throughput,
                                                     self.errors,
                                                     self.transaction_rate))


class NetperfAssertion(object):
    """Defines a set of expectations for netperf results."""

    def __init__(self, duration_min=None, duration_max=None,
                 throughput_min=None, throughput_max=None,
                 error_min=None, error_max=None,
                 transaction_rate_min=None, transaction_rate_max=None):
        """Construct a NetperfAssertion.

        Leaving bounds undefined sets them to values which are permissive.

        @param duration_min float minimal test duration in seconds.
        @param duration_max float maximal test duration in seconds.
        @param throughput_min float minimal throughput in Mbps.
        @param throughput_max float maximal throughput in Mbps.
        @param error_min int minimal number of UDP frame errors.
        @param error_max int max number of UDP frame errors.
        @param transaction_rate_min float minimal number of transactions
                per second.
        @param transaction_rate_max float max number of transactions per second.

        """
        self.duration_bounds = (duration_min, duration_max)
        self.throughput_bounds = (throughput_min, throughput_max)
        self.error_bounds = (error_min, error_max)
        self.transaction_rate_bounds = (transaction_rate_min,
                                        transaction_rate_max)


    def _passes(self, value, bounds):
        if bounds[0] is None and bounds[1] is None:
            return True

        if value is None:
            # We have bounds requirements, but no value to check?
            return False

        if bounds[0] is not None and bounds[0] > value:
            return False

        if bounds[1] is not None and bounds[1] < value:
            return False

        return True


    def passes(self, result):
        """Check that a result matches the given assertion.

        @param result NetperfResult object produced by a test.
        @return True iff all this assertion passes for the give result.

        """
        if (self._passes(result.duration_seconds, self.duration_bounds) and
            self._passes(result.throughput, self.throughput_bounds) and
            self._passes(result.errors, self.error_bounds) and
            self._passes(result.transaction_rate,
                         self.transaction_rate_bounds)):
            return True

        return False


    def __repr__(self):
        return ('%s(duration_min=%r, duration_max=%r, '
                'thoughput_min=%r, throughput_max=%r, '
                'error_min=%r, error_max=%r, '
                'transaction_rate_min=%r, transaction_rate_max=%r)' % (
                    self.__class__.__name__,
                    self.duration_bounds[0], self.duration_bounds[1],
                    self.throughput_bounds[0], self.throughput_bounds[1],
                    self.error_bounds[0], self.error_bounds[1],
                    self.transaction_rate_bounds[0],
                    self.transaction_rate_bounds[1]))


class NetperfConfig(object):
    """Defines a single netperf run."""

    DEFAULT_TEST_TIME = 15
    # Measures how many times we can connect, request a byte, and receive a
    # byte per second.
    TEST_TYPE_TCP_CRR = 'TCP_CRR'
    # MAERTS is stream backwards.  Measure bitrate of a stream from the netperf
    # server to the client.
    TEST_TYPE_TCP_MAERTS = 'TCP_MAERTS'
    # Measures how many times we can request a byte and receive a byte per
    # second.
    TEST_TYPE_TCP_RR = 'TCP_RR'
    # This is like a TCP_STREAM test except that the netperf client will use
    # a platform dependent call like sendfile() rather than the simple send()
    # call.  This can result in better performance.
    TEST_TYPE_TCP_SENDFILE = 'TCP_SENDFILE'
    # Measures throughput sending bytes from the client to the server in a
    # TCP stream.
    TEST_TYPE_TCP_STREAM = 'TCP_STREAM'
    # Measures how many times we can request a byte from the client and receive
    # a byte from the server.  If any datagram is dropped, the client or server
    # will block indefinitely.  This failure is not evident except as a low
    # transaction rate.
    TEST_TYPE_UDP_RR = 'UDP_RR'
    # Test UDP throughput sending from the client to the server.  There is no
    # flow control here, and generally sending is easier that receiving, so
    # there will be two types of throughput, both receiving and sending.
    TEST_TYPE_UDP_STREAM = 'UDP_STREAM'
    # Different kinds of tests have different output formats.
    REQUEST_RESPONSE_TESTS = [ TEST_TYPE_TCP_CRR,
                               TEST_TYPE_TCP_RR,
                               TEST_TYPE_UDP_RR ]
    TCP_STREAM_TESTS = [ TEST_TYPE_TCP_MAERTS,
                         TEST_TYPE_TCP_SENDFILE,
                         TEST_TYPE_TCP_STREAM ]
    UDP_STREAM_TESTS = [ TEST_TYPE_UDP_STREAM ]


    @staticmethod
    def _assert_is_valid_test_type(test_type):
        """Assert that |test_type| is one of TEST_TYPE_* above.

        @param test_type string test type.

        """
        if (test_type not in NetperfConfig.REQUEST_RESPONSE_TESTS and
            test_type not in NetperfConfig.TCP_STREAM_TESTS and
            test_type not in NetperfConfig.UDP_STREAM_TESTS):
            raise error.TestFail('Invalid netperf test type: %r.' % test_type)


    def __init__(self, test_type, server_serves=True, test_time=None):
        """Construct a NetperfConfig.

        @param test_type string one of TEST_TYPE_* above.
        @param server_serves bool True iff server is acting as the netperf
            server.
        @param test_time int number of seconds to run the test for.

        """
        self._assert_is_valid_test_type(test_type)
        self.test_type = test_type
        self.server_serves = server_serves
        self.test_time = test_time or self.DEFAULT_TEST_TIME


    def __repr__(self):
        return '%s(test_type=%r, server_serves=%r, test_time=%r' % (
                self.__class__.__name__,
                self.test_type,
                self.server_serves,
                self.test_time)


class NetperfRunner(object):
    """Delegate to run netperf on a client/server pair."""

    NETPERF_DATA_PORT = 12866
    NETPERF_PORT = 12865
    NETSERV_STARTUP_WAIT_TIME = 3


    def __init__(self, client, server):
        """Construct a NetperfRunner.

        @param client WiFiClient object.
        @param server LinuxServer object.

        """
        self._client_proxy = client
        self._server_proxy = server


    def _run_body(self, client_host, server_host, netperf, netserv, timeout):
        """Actually run the commands on the remote hosts.

        This method contains all the calls for a netperf run that are likely to
        fail.  As such, it should only be called in a context where we know that
        suitable cleanup will happen in case of a failure.

        @param client_host Host object representing the 'client' test role.
        @param server_host Host object representing the 'server' test role.
        @param netperf string complete command with args to start netperf.
        @param netserv string complete command with args to start netserv.
        @param timeout int number of seconds to give the netperf command.
        @return tuple (raw netperf output, duration of run in seconds).

        """
        logging.info('Starting netserver with command %s.', netserv)
        server_host.run(netserv)
        # Wait for the netserv to come up.
        time.sleep(self.NETSERV_STARTUP_WAIT_TIME)
        logging.info('Running netperf client with command %s.', netperf)
        start_time = time.time()
        result = client_host.run(netperf, timeout=timeout)
        duration = time.time() - start_time
        return result.stdout, duration


    def run(self, config):
        """Run netperf.

        @param config NetperfConfig defines the parameters of the test.
        @return NetperfResult summarizing the resulting test.

        """
        if config.server_serves:
            server_host = self._server_proxy.host
            client_host = self._client_proxy.host
            command_netserv = self._server_proxy.cmd_netserv
            command_netperf = self._client_proxy.command_netperf
            target_ip = self._server_proxy.wifi_ip
        else:
            server_host = self._client_proxy.host
            client_host = self._server_proxy.host
            command_netserv = self._client_proxy.command_netserv
            command_netperf = self._server_proxy.cmd_netperf
            target_ip = self._client_proxy.wifi_ip

        netserv = '%s -p %d &> /dev/null' % (command_netserv, self.NETPERF_PORT)
        netperf = '%s -H %s -p %s -t %s -l %d -- -P 0,%d' % (
                command_netperf,
                target_ip,
                self.NETPERF_PORT,
                config.test_type,
                config.test_time,
                self.NETPERF_DATA_PORT)
        self._client_proxy.firewall_open('tcp', self._server_proxy.wifi_ip)
        self._client_proxy.firewall_open('udp', self._server_proxy.wifi_ip)
        try:
            raw_result,duration = self._run_body(
                    client_host, server_host, netperf, netserv,
                    config.test_time + self.NETSERV_STARTUP_WAIT_TIME)
        finally:
            server_host.run('pkill %s' % os.path.basename(command_netserv))
            self._client_proxy.firewall_cleanup()
        return NetperfResult.from_netperf_results(config.test_type, raw_result,
                                                  duration)
