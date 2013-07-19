# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import math
import re

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error


class PingConfig(object):
    """Describes the parameters for a ping command."""

    DEFAULT_COUNT = 10
    PACKET_WAIT_MARGIN_SECONDS = 10

    @property
    def ping_args(self):
        """@return list of parameters to ping."""
        args = []
        args.append('-c %d' % self.count)
        if self.size is not None:
            args.append('-s %d' % self.size)
        if self.interval is not None:
            args.append('-i %f' % self.interval)
        if self.qos is not None:
            if self.qos == 'be':
                args.append('-Q 0x04')
            elif self.qos == 'bk':
                args.append('-Q 0x02')
            elif self.qos == 'vi':
                args.append('-Q 0x08')
            elif self.qos == 'vo':
                args.append('-Q 0x10')
            else:
                raise error.TestFail('Unknown QoS value: %s' % self.qos)

        # The last argument is the IP addres to ping.
        args.append(self.target_ip)
        return args


    def __init__(self, target_ip, count=DEFAULT_COUNT, size=None,
                 interval=None, qos=None,
                 ignore_status=False, ignore_result=False):
        super(PingConfig, self).__init__()
        self.target_ip = target_ip
        self.count = count
        self.size = size
        self.interval = interval
        if qos:
            qos = qos.lower()
        self.qos = qos
        self.ignore_status = ignore_status
        self.ignore_result = ignore_result
        interval_seconds = self.interval or 1
        command_time = math.ceil(interval_seconds * self.count)
        self.command_timeout_seconds = int(command_time +
                                           self.PACKET_WAIT_MARGIN_SECONDS)


class PingResult(object):
    """Represents a parsed ping command result.

    On error, some statistics may be missing entirely from the output.

    An example of output with some errors is:

    PING 192.168.0.254 (192.168.0.254) 56(84) bytes of data.
    From 192.168.0.124 icmp_seq=1 Destination Host Unreachable
    From 192.168.0.124 icmp_seq=2 Destination Host Unreachable
    From 192.168.0.124 icmp_seq=3 Destination Host Unreachable
    64 bytes from 192.168.0.254: icmp_req=4 ttl=64 time=1171 ms
    [...]
    64 bytes from 192.168.0.254: icmp_req=10 ttl=64 time=1.95 ms

    --- 192.168.0.254 ping statistics ---
    10 packets transmitted, 7 received, +3 errors, 30% packet loss, time 9007ms
    rtt min/avg/max/mdev = 1.806/193.625/1171.174/403.380 ms, pipe 3

    A more normal run looks like:

    PING google.com (74.125.239.137) 56(84) bytes of data.
    64 bytes from 74.125.239.137: icmp_req=1 ttl=57 time=1.77 ms
    64 bytes from 74.125.239.137: icmp_req=2 ttl=57 time=1.78 ms
    [...]
    64 bytes from 74.125.239.137: icmp_req=5 ttl=57 time=1.79 ms

    --- google.com ping statistics ---
    5 packets transmitted, 5 received, 0% packet loss, time 4007ms
    rtt min/avg/max/mdev = 1.740/1.771/1.799/0.042 ms

    """

    @property
    def old_style_output(self):
        """@return old style dict of ping results."""
        return {'xmit': str(self.sent),
                'recv': str(self.received),
                'loss': str(self.loss),
                'min': str(self.min_latency),
                'avg': str(self.avg_latency),
                'max': str(self.max_latency),
                'dev': str(self.dev_latency)}


    def __init__(self,ping_output):
        """Construct a PingResult.

        @param ping_output string stdout from a ping command.

        """
        super(PingResult, self).__init__()
        m = re.search('([0-9]*) packets transmitted, '
                      '([0-9]*) received, '
                      '(\\+([0-9]*) errors, )?'
                      '([0-9]*)% packet loss',
                      ping_output)
        if m is None:
            raise error.TestFail('Failed to parse transmission statistics.')

        self.sent = int(m.group(1))
        self.received = int(m.group(2))
        self.loss = int(m.group(5))
        m = re.search('(round-trip|rtt) min[^=]*= '
                      '([0-9.]*)/([0-9.]*)/([0-9.]*)/([0-9.]*)', ping_output)
        if m is not None:
            self.min_latency = float(m.group(2))
            self.avg_latency = float(m.group(3))
            self.max_latency = float(m.group(4))
            self.dev_latency = float(m.group(5))
        else:
            if self.received > 0:
                raise error.TestFail('Failed to parse latency statistics.')

            self.min_latency = -1.0
            self.avg_latency = -1.0
            self.max_latency = -1.0
            self.dev_latency = -1.0


    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ', '.join(['%s=%r' % item
                                      for item in vars(self).iteritems()]))


class PingRunner(object):
    """Delegate to run the ping command on a local or remote host."""
    DEFAULT_PING_COMMAND = 'ping'
    PING_LOSS_THRESHOLD = 20  # A percentage.


    def __init__(self, command_ping=DEFAULT_PING_COMMAND, host=None):
        """Construct a PingRunner.

        @param command_ping optional path or alias of the ping command.
        @param host optional host object when a remote host is desired.

        """
        super(PingRunner, self).__init__()
        self._run = utils.run
        if host is not None:
            self._run = host.run
        self.command_ping = command_ping


    def ping(self, ping_config):
        """Run ping with the given |ping_config|.

        Will assert that the ping had reasonable levels of loss unless
        requested not to in |ping_config|.

        @param ping_config PingConfig object describing the ping to run.

        """
        command_pieces = [self.command_ping] + ping_config.ping_args
        command = ' '.join(command_pieces)
        command_result = self._run(command,
                                   timeout=ping_config.command_timeout_seconds,
                                   ignore_status=ping_config.ignore_status)
        ping_result = PingResult(command_result.stdout)
        if ping_config.ignore_result:
            return ping_result

        if ping_result.loss > self.PING_LOSS_THRESHOLD:
            raise error.TestFail('Lost ping packets: %r.' % ping_result)

        logging.info('Ping successful.')
        return ping_result
