# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import dpkt
import fake_host
import socket
import zeroconf


FAKE_HOSTNAME = 'fakehost1'

FAKE_IPADDR = '192.168.11.22'


class TestZeroconfDaemon(unittest.TestCase):
    """Test class for ZeroconfDaemon."""

    def setUp(self):
        self._host = fake_host.FakeHost(FAKE_IPADDR)
        self._zero = zeroconf.ZeroconfDaemon(self._host, FAKE_HOSTNAME)


    def _query_A(self, name):
        """Returns the list of A records matching the given name.

        @param name: A domain name.
        @return a list of dpkt.dns.DNS.RR objects, one for each matching record.
        """
        q = dpkt.dns.DNS.Q(name=name, type=dpkt.dns.DNS_A)
        return self._zero._process_A(q)


    def testProperties(self):
        """Test the initial properties set by the constructor."""
        self.assertEqual(self._zero.host, self._host)
        self.assertEqual(self._zero.hostname, FAKE_HOSTNAME)
        self.assertEqual(self._zero.domain, 'local') # Default domain
        self.assertEqual(self._zero.full_hostname, FAKE_HOSTNAME + '.local')


    def testSocketInit(self):
        """Test that the constructor listens for mDNS traffic."""

        # Should create an UDP socket and bind it to the mDNS address and port.
        self.assertEqual(len(self._host._sockets), 1)
        sock = self._host._sockets[0]

        self.assertEqual(sock._family, socket.AF_INET) # IPv4
        self.assertEqual(sock._sock_type, socket.SOCK_DGRAM) # UDP

        # Check it is listening for UDP packets on the mDNS address and port.
        self.assertTrue(sock._bound)
        self.assertEqual(sock._bind_ip_addr, '224.0.0.251') # mDNS address
        self.assertEqual(sock._bind_port, 5353) # mDNS port
        self.assertTrue(callable(sock._bind_recv_callback))


    def testRecordsInit(self):
        """Test the A record of the host is registered."""
        host_A = self._query_A(self._zero.full_hostname)
        self.assertGreater(len(host_A), 0)

        record = host_A[0]
        # Check the hostname and the packed IP address.
        self.assertEqual(record.name, self._zero.full_hostname)
        self.assertEqual(record.ip, socket.inet_aton(self._host.ip_addr))


if __name__ == '__main__':
    unittest.main()
