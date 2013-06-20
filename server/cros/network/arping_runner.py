# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros import wifi_test_utils


class ArpingRunner(object):
    """Delegate to run arping on a remote host."""

    DEFAULT_COUNT = 10
    SSH_TIMEOUT_MARGIN = 2


    def __init__(self, host, ping_interface):
        self._host = host
        self._arping_command = wifi_test_utils.must_be_installed(
                host, '/usr/bin/arping')
        self._ping_interface = ping_interface


    def arping(self, target_ip, count=None, timeout_seconds=None):
        """Run arping on a remote host.

        @param target_ip: string IP address to use as the ARP target.
        @param count: int number of ARP packets to send.  The command
            will take roughly |count| seconds to complete, since arping
            sends a packet out once a second.
        @param timeout_seconds: int number of seconds to wait for arping
            to complete.  Override the default of one second per packet.
            Note that this doesn't change packet spacing.

        """
        if count is None:
            count = self.DEFAULT_COUNT
        if timeout_seconds is None:
            timeout_seconds  = count
        command_pieces = [self._arping_command]
        command_pieces.append('-b')  # Default to only sending broadcast ARPs.
        command_pieces.append('-w %d' % timeout_seconds)
        command_pieces.append('-c %d' % count)
        command_pieces.append('-I %s %s' % (self._ping_interface, target_ip))
        result = self._host.run(
                ' '.join(command_pieces),
                timeout=timeout_seconds + self.SSH_TIMEOUT_MARGIN,
                ignore_status=True)
        return ArpingResult(result.stdout)


class ArpingResult(object):
    """Can parse raw arping output and present a summary."""

    DEFAULT_LOSS_THRESHOLD = 30.0


    def __init__(self, stdout):
        """Construct an ArpingResult from the stdout of arping.

        A successful run looks something like this:

        ARPING 172.22.75.254 from 172.22.73.124 eth0
        Unicast reply from 172.22.75.254 [00:00:0C:9F:F0:21]  1.447ms
        Unicast reply from 172.22.75.254 [00:00:0C:9F:F0:21]  1.275ms
        Unicast reply from 172.22.75.254 [00:00:0C:9F:F0:21]  1.388ms
        Sent 3 probes (3 broadcast(s))
        Received 3 response(s)

        @param stdout string raw stdout of arping command.

        """
        latencies = []
        responders = set()
        num_sent = None
        regex = re.compile(r'(([0-9]{1,3}\.){3}[0-9]{1,3}) '
                           r'\[(([0-9A-F]{2}:){5}[0-9A-F]{2})\] +'
                           r'([0-9\.]+)ms$')
        for line in stdout.splitlines():
            if line.find('Unicast reply from') == 0:
                match = re.search(regex, line.strip())
                responder_ip = match.group(1)  # Maybe useful in the future?
                responder_mac = match.group(3)
                latency = float(match.group(5))
                latencies.append(latency)
                responders.add(responder_mac)
            elif line.find('Sent ') == 0:
                num_sent = int(line.split()[1])
            elif line.find('Received ') == 0:
                count = int(line.split()[1])
                if count != len(latencies):
                    raise error.TestFail('Failed to parse accurate latencies '
                                         'from stdout: %r.  Got %d, '
                                         'wanted %d.' % (stdout, len(latencies),
                                                         count))
        if num_sent is None:
            raise error.TestFail('Failed to parse number of arpings sent '
                                 'from %r' % stdout)

        if num_sent < 1:
            raise error.TestFail('No arpings sent.')

        self.loss = 100.0 * float(num_sent - len(latencies)) / num_sent
        self.average_latency = 0.0
        if latencies:
            self.average_latency = sum(latencies) / len(latencies)
        self.latencies = latencies
        self.responders = responders


    def was_successful(self, max_average_latency=None, valid_responders=None,
                       max_loss=DEFAULT_LOSS_THRESHOLD):
        """Checks if the arping was some definition of successful.

        @param max_average_latency float maximum value for average latency in
                milliseconds.
        @param valid_responders iterable object of responder MAC addresses.
                We'll check that we got only responses from valid responders.
        @param max_loss float maximum loss expressed as a percentage.
        @return True iff all criterion set to not None values hold.

        """
        if (max_average_latency is not None and
                self.average_latency > max_average_latency):
            return False

        if (valid_responders is not None and
                self.responders.difference(valid_responders)):
            return False

        if max_loss is not None and self.loss > max_loss:
            return False

        return True


    def __repr__(self):
        return ('%s(loss=%r, average_latency=%r, latencies=%r, responders=%r)' %
                (self.__class__.__name__, self.loss, self.average_latency,
                 self.latencies, self.responders))
