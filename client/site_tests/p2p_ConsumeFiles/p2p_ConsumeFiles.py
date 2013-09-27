# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import sys
import tempfile

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.cros import service_stopper, avahi_utils
from autotest_lib.client.cros.netprotos import cros_p2p, zeroconf


P2P_CLIENT = '/usr/sbin/p2p-client'


class p2p_ConsumeFiles(test.test):
    """The P2P Client class tester.

    Creates a fake network of peers with lansim and tests if p2p-client can
    discover files on that network.
    """
    version = 1

    def setup(self):
        self.job.setup_dep(['lansim'])


    def initialize(self):
        dep = 'lansim'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        logging.info('lansim is at %s', dep_dir)
        self.job.install_pkg(dep, 'dep', dep_dir)

        # Import the lansim modules installed on lansim/build/
        sys.path.append(os.path.join(dep_dir, 'build'))
        from lansim import tuntap

        # Ensure p2p and avahi aren't running.
        self._services = service_stopper.ServiceStopper(['p2p', 'avahi'])
        self._services.stop_services()

        # Initialize avahi-daemon listenning only on the fake TAP interface.
        self._tap = tuntap.TunTap(tuntap.IFF_TAP, name='faketap')

        # The network 169.254/16 shouldn't clash with other real services. We
        # use a /24 subnet of it here.
        self._tap.set_addr("169.254.10.1", mask=24)
        self._tap.up()

        # Re-launch avahi-daemon with custom options.
        opts = [('server', 'allow-interfaces', self._tap.name),
                ('server', 'deny-interfaces', None)]
        conf = avahi_utils.avahi_config(opts)
        avahi_utils.avahi_start(config_file=conf)
        os.unlink(conf)


    def cleanup(self):
        avahi_utils.avahi_stop()

        self._tap.down()

        if self._services:
            self._services.restore_services()


    def _run_p2p_client(self, args, timeout=10., ignore_status=False):
        """Run p2p-client with the provided arguments.

        @param args: list of strings, each one representing an argument.
        @param timeout: Timeout for p2p-client in seconds before it's killed.
        @return: the return value of the process and the stdout content.
        """
        fd, tempfn = tempfile.mkstemp(prefix='p2p-output')
        ret = utils.run(
                P2P_CLIENT, args=args, timeout=timeout,
                stdout_tee=open(tempfn, 'w'), ignore_status=True,
                stderr_tee=sys.stdout)
        url = os.fdopen(fd).read()
        os.unlink(tempfn)

        if not ignore_status and ret.exit_status != 0:
            raise error.TestFail('p2p-client %s finished with value: %d' % (
                                 ' '.join(args), ret.exit_status))

        return ret.exit_status, url


    def run_once(self):
        from lansim import simulator, host

        sim = simulator.SimulatorThread(self._tap)
        # Create three peers host-a, host-b and host-c sharing a set of files.
        # This first block creates the fake host on the simulator. For clarity
        # and easier debug, note that the last octect on the IPv4 address is the
        # ASCII for a, b and c respectively.
        peer_a = host.SimpleHost(sim, '94:EB:2C:00:00:61', '169.254.10.97')
        peer_b = host.SimpleHost(sim, '94:EB:2C:00:00:62', '169.254.10.98')
        peer_c = host.SimpleHost(sim, '94:EB:2C:00:00:63', '169.254.10.99')

        # Run a userspace implementation of avahi + p2p-server on the fake
        # hosts. This announces the P2P service on each fake host.
        zero_a = zeroconf.ZeroconfDaemon(peer_a, 'host-a')
        zero_b = zeroconf.ZeroconfDaemon(peer_b, 'host-b')
        zero_c = zeroconf.ZeroconfDaemon(peer_c, 'host-c')

        cros_a = cros_p2p.CrosP2PDaemon(zero_a)
        cros_b = cros_p2p.CrosP2PDaemon(zero_b)
        cros_c = cros_p2p.CrosP2PDaemon(zero_c)

        # Add files to each host. All the three hosts share the file "everyone"
        # with different size, used to test the minimum-size argument.
        # host-a and host-b share another file only-a and only-b respectively,
        # used to check that the p2p-client picks the right peer.
        cros_a.add_file('everyone', 1000)
        cros_b.add_file('everyone', 10000)
        cros_c.add_file('everyone', 20000)

        cros_a.add_file('only-a', 5000)

        cros_b.add_file('only-b', 8000)

        # Initially set the number of connections on the network to a low number
        # (two) that later will be increased to test if p2p-client hangs when
        # there are too many connections.
        cros_a.set_num_connections(1)
        cros_c.set_num_connections(1)

        sim.start()

        ### Request a file shared from only one peer.
        _ret, url = self._run_p2p_client(
                args=('--get-url=only-a',), timeout=10.)

        if url.strip() != 'http://169.254.10.97:16725/only-a':
            raise error.TestFail('Received unknown url: "%s"' % url)

        ### Check that the num_connections is reported properly.
        _ret, conns = self._run_p2p_client(args=('--num-connections',),
                                          timeout=10.)
        if conns.strip() != '2':
            raise error.TestFail('Wrong number of connections reported: %s' %
                                 conns)

        ### Request a file shared from a peer with enough of the file.
        _ret, url = self._run_p2p_client(
                args=('--get-url=everyone', '--minimum-size=15000'),
                timeout=10.)

        if url.strip() != 'http://169.254.10.99:16725/everyone':
            raise error.TestFail('Received unknown url: "%s"' % url)

        ### Request too much bytes of an existing file.
        ret, url = self._run_p2p_client(
                args=('--get-url=only-b', '--minimum-size=10000'),
                timeout=10., ignore_status=True)

        if url:
            raise error.TestFail('Received url but expected none: "%s"' % url)
        if ret == 0:
            error.TestFail('p2p-client returned no URL, but without an error.')

        ### Check that p2p-client hangs while waiting for a peer when there are
        ### too many connections.
        cros_a.set_num_connections(99)

        ret, url = self._run_p2p_client(
                args=('--get-url=only-b',), timeout=5., ignore_status=True)
        if ret == 0:
            error.TestFail('p2p-client finished but should have waited for '
                           'num_connections to drop.')

        sim.stop()
        sim.join()

        if sim.error:
            raise error.TestError('SimulatorThread ended with an exception: %r'
                                  % sim.error)
