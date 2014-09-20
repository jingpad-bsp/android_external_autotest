# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import netblock
from autotest_lib.client.cros import network_chroot
from autotest_lib.client.cros import service_stopper
from autotest_lib.client.cros import tcpdump
from autotest_lib.client.cros import virtual_ethernet_pair
from autotest_lib.client.cros.tendo import peerd_helper

class peerd_AdvertiseServices(test.test):
    """Test that peerd can correctly advertise services over mDNS."""
    version = 1

    SERVICES_TO_STOP = ['p2p', 'peerd', 'avahi']
    # This side has to be called something special to avoid shill touching it.
    MONITOR_IF_IP = netblock.Netblock('10.9.8.1/24')
    MONITOR_IF_NAME = 'pseudoethernet1'
    # We'll drop the Avahi side into our network namespace.
    AVAHI_IF_IP = netblock.Netblock('10.9.8.2/24')
    AVAHI_IF_NAME = 'pseudoethernet0'
    TCPDUMP_FILE_PATH = '/tmp/peerd_dump.pcap'
    AVAHI_CONFIG_FILE = 'etc/avahi/avahi-daemon.conf'
    AVAHI_CONFIGS = {
        AVAHI_CONFIG_FILE :
            '[server]\n'
                'host-name-from-machine-id=yes\n'
                'browse-domains=\n'
                'use-ipv4=yes\n'
                'use-ipv6=no\n'
                'ratelimit-interval-usec=1000000\n'
                'ratelimit-burst=1000\n'
            '[wide-area]\n'
                'enable-wide-area=no\n'
            '[publish]\n'
                'publish-hinfo=no\n'
                'publish-workstation=no\n'
                'publish-aaaa-on-ipv4=no\n'
                'publish-a-on-ipv6=no\n'
            '[rlimits]\n'
                'rlimit-core=0\n'
                'rlimit-data=4194304\n'
                'rlimit-fsize=1024\n'
                'rlimit-nofile=768\n'
                'rlimit-stack=4194304\n'
                'rlimit-nproc=10\n',

        'etc/passwd' :
            'root:x:0:0:root:/root:/bin/bash\n'
            'avahi:*:238:238::/dev/null:/bin/false\n',

        'etc/group' :
            'avahi:x:238:\n',
    }
    AVAHI_LOG_FILE = '/var/log/avahi.log'
    AVAHI_PID_FILE = 'var/run/avahi-daemon/pid'


    def initialize(self):
        self._services = None
        self._vif = None
        self._tcpdump = None
        self._chroot = None
        self._peerd = None
        # Prevent weird interactions between services which talk to Avahi.
        # TODO(wiley) Does Chrome need to die here as well?
        self._services = service_stopper.ServiceStopper(
                self.SERVICES_TO_STOP)
        self._services.stop_services()
        # We don't want Avahi talking to the real world, so give it a nice
        # fake interface to use.  We'll watch the other half of the pair.
        self._vif = virtual_ethernet_pair.VirtualEthernetPair(
                interface_name=self.MONITOR_IF_NAME,
                peer_interface_name=self.AVAHI_IF_NAME,
                interface_ip=self.MONITOR_IF_IP.netblock,
                peer_interface_ip=self.AVAHI_IF_IP.netblock,
                # Moving one end into the chroot causes errors.
                ignore_shutdown_errors=True)
        self._vif.setup()
        if not self._vif.is_healthy:
            raise error.TestError('Failed to setup virtual ethernet pair.')
        # By default, take a packet capture of everything Avahi sends out.
        self._tcpdump = tcpdump.Tcpdump(self.MONITOR_IF_NAME,
                                        self.TCPDUMP_FILE_PATH)
        # We're going to run Avahi in a network namespace to avoid interactions
        # with the outside world.
        self._chroot = network_chroot.NetworkChroot(self.AVAHI_IF_NAME,
                                                    self.AVAHI_IF_IP.addr,
                                                    self.AVAHI_IF_IP.prefix_len)
        self._chroot.add_config_templates(self.AVAHI_CONFIGS)
        self._chroot.add_root_directories(['etc/avahi', 'etc/avahi/services'])
        self._chroot.add_copied_config_files(['etc/resolv.conf',
                                              'etc/avahi/hosts'])
        self._chroot.add_startup_command(
                '/usr/sbin/avahi-daemon --file=/%s &> %s' %
                (self.AVAHI_CONFIG_FILE, self.AVAHI_LOG_FILE))
        self._chroot.bridge_dbus_namespaces()
        self._chroot.startup()
        # Start up a cleaned up peerd with really verbose logging.
        self._peerd = peerd_helper.make_helper(start_instance=True,
                                               verbosity_level=3)


    def cleanup(self):
        if self._peerd:
            self._peerd.close()
        if self._chroot:
            # TODO(wiley) This is sloppy.  Add a helper to move the logs over.
            for line in self._chroot.get_log_contents().splitlines():
                logging.debug(line)
            self._chroot.kill_pid_file(self.AVAHI_PID_FILE)
            self._chroot.shutdown()
        if self._tcpdump:
            self._tcpdump.stop()
        if self._vif:
            self._vif.teardown()
        if self._services:
            self._services.restore_services()


    def run_once(self):
        service_token = self._peerd.expose_service(
                'test-service-0', {'some_data': 'a_value'})
        # TODO(wiley): set up mDNS listener on our half of ethernet pair.
        # TODO(wiley): wait for advertisements of that service to appear from avahi
