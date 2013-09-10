# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import subprocess
import unittest

from lansim import host
from lansim import simulator
from lansim import tuntap


class SimulatorTest(unittest.TestCase):
    """Unit tests for the Simulator class."""

    def setUp(self):
        """Creates a Simulator under test over a TAP device."""
        self._tap = tuntap.TunTap(tuntap.IFF_TAP, name="faketap")
        # According to RFC 3927 (Dynamic Configuration of IPv4 Link-Local
        # Addresses), a host can pseudorandomly assign an IPv4 address on the
        # 169.254/16 network to communicate with other devices on the same link
        # on absence of a DHCP server and other source of network configuration.
        # The tests on this class explicitly specify the interface to use, so
        # they can run in parallel even when there are more than one interface
        # with the same IPv4 address. A TUN/TAP interface with an IPv4 address
        # on this range shouldn't collide with any useful service running on a
        # different (physical) interface.
        self._tap.set_addr('169.254.11.11')
        self._tap.up()

        self._sim = simulator.Simulator(self._tap)


    def tearDown(self):
        """Stops and destroy the interface."""
        self._tap.down()


    def testTimeout(self):
        """Tests that the Simulator can start and run for a short time."""
        # Run for at most 100ms and finish the test. This implies that the
        # stop() method works.
        self._sim.run(timeout=0.1)

    def testHost(self):
        """Tests that the Simulator can add rules from the SimpleHost."""
        # The IP and MAC addresses simulated are unknown to the rest of the
        # system as they only live on this interface. Again, any IP on the
        # network 169.254/16 should not cause any problem with other services
        # running on this host.
        host.SimpleHost(self._sim, '12:34:56:78:90:AB', '169.254.11.22')
        self._sim.run(timeout=0.1)


class SimulatorThreadTest(unittest.TestCase):
    """Unit tests for the SimulatorThread class."""

    def setUp(self):
        """Creates a SimulatorThread under test over a TAP device."""
        self._tap = tuntap.TunTap(tuntap.IFF_TAP, name="faketap")
        # See note about IP addresses on SimulatorTest.setUp().
        self._tap.set_addr('169.254.11.11')
        self._tap.up()

        self._sim = simulator.SimulatorThread(self._tap)


    def tearDown(self):
        """Stops and destroy the thread."""
        self._sim.stop() # stop() can be called even if the thread is stopped.
        self._sim.join()
        self._tap.down()


    def testARPPing(self):
        """Test that the simulator properly handles a ARP request/response."""
        host.SimpleHost(self._sim, '12:34:56:78:90:22', '169.254.11.22')
        host.SimpleHost(self._sim, '12:34:56:78:90:33', '169.254.11.33')
        host.SimpleHost(self._sim, '12:34:56:78:90:44', '169.254.11.33')

        self._sim.start()
        # arping and wait for one second for the responses.
        out = subprocess.check_output(
                ['arping', '-I', self._tap.name, '169.254.11.22',
                 '-c', '1', '-w', '1'])
        resp = [line for line in out.splitlines() if 'Unicast reply' in line]
        self.assertEqual(len(resp), 1)
        self.assertTrue(resp[0].startswith(
                'Unicast reply from 169.254.11.22 [12:34:56:78:90:22]'))

        out = subprocess.check_output(
                ['arping', '-I', self._tap.name, '169.254.11.33',
                 '-c', '1', '-w', '1'])
        resp = [line for line in out.splitlines() if 'Unicast reply' in line]
        self.assertEqual(len(resp), 2)
        resp.sort()
        self.assertTrue(resp[0].startswith(
                'Unicast reply from 169.254.11.33 [12:34:56:78:90:33]'))
        self.assertTrue(resp[1].startswith(
                'Unicast reply from 169.254.11.33 [12:34:56:78:90:44]'))


if __name__ == '__main__':
    unittest.main()

