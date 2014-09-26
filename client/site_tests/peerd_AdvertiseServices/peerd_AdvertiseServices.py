# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dpkt
import logging
import time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import netblock
from autotest_lib.client.cros import avahi_utils
from autotest_lib.client.cros import network_chroot
from autotest_lib.client.cros import service_stopper
from autotest_lib.client.cros import tcpdump
from autotest_lib.client.cros import virtual_ethernet_pair
from autotest_lib.client.cros.netprotos import interface_host
from autotest_lib.client.cros.netprotos import zeroconf
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
    AVAHI_UP_TIMEOUT_SECONDS = 10
    FAKE_HOST_HOSTNAME = 'test-host'
    POLLING_PERIOD_SECONDS = 0.2
    TEST_TIMEOUT_SECONDS = 30
    PEERD_SERVICE_ID = 'test-service-0'
    PEERD_SERVICE_INFO = {'some_data': 'a value',
                          'other_data': 'another value'}
    QUERY_INTERVAL_SECONDS = 3.0


    def initialize(self):
        self._services = None
        self._vif = None
        self._tcpdump = None
        self._chroot = None
        self._peerd = None
        self._avahi_proxy = None
        self._host = None
        self._zc_listener = None
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
        # Wait for Avahi to come up, claim its DBus name, settle on a hostname.
        start_time = time.time()
        while time.time() - start_time < self.AVAHI_UP_TIMEOUT_SECONDS:
            if avahi_utils.avahi_ping():
                break
            time.sleep(self.POLLING_PERIOD_SECONDS)
        else:
            raise error.TestFail('Avahi did not come up in time.')
        self._avahi_hostname = avahi_utils.avahi_get_hostname()
        self._dns_domain = avahi_utils.avahi_get_domain_name()
        if not self._avahi_hostname or not self._dns_domain:
            raise error.TestFail('Failed to get hostname/domain from avahi.')
        # Listen on our half of the interface pair for mDNS advertisements.
        self._host = interface_host.InterfaceHost(self.MONITOR_IF_NAME)
        self._zc_listener = zeroconf.ZeroconfDaemon(self._host,
                                                    self.FAKE_HOST_HOSTNAME)


    def cleanup(self):
        if self._host:
            self._host.close()
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


    def _ask_for_record(self, record_name, record_type):
        """Ask for a record, and query for it if we don't have it.

        @param record_name: string name of record (e.g. the complete host name
                            for A records.
        @param record_type: one of dpkt.dns.DNS_*.
        @return list of matching records.

        """
        found_records = self._zc_listener.cached_results(
                record_name, record_type)
        if len(found_records) > 1:
            logging.warning('Found multiple records with name=%s and type=%r',
                            record_name, record_type)
        if found_records:
            return found_records
        logging.debug('Did not see record with name=%s and type=%r',
                      record_name, record_type)
        desired_records = [(record_name, record_type)]
        self._zc_listener.send_request(desired_records)
        return []


    def _found_desired_records(self):
        """Verifies that avahi has all the records we care about.

        Asks the |self._zc_listener| for records we expect to correspond
        to our test service.  Will trigger queries if we don't find the
        expected records.

        @return True if we have all expected records, False otherwise.

        """
        hostname = '%s.%s' % (self._avahi_hostname, self._dns_domain)
        logging.debug('Looking for records for %s.', hostname)
        logging.error('WILEY: Have records: %r', self._zc_listener._peer_records)
        # First, check that Avahi is doing the simple things and publishing
        # an A record.
        records_A = self._ask_for_record(hostname, dpkt.dns.DNS_A)
        if not records_A:
            return False
        if records_A[0].data != self.AVAHI_IF_IP.addr:
            raise error.TestFail('Did not see expected A record with value %s',
                                 self.AVAHI_IF_IP.addr)
        # If we can see Avahi publishing that it's there, check that it has
        # a PTR to the unique name of the interesting service.
        PTR_name = '_%s._tcp.%s' % (self.PEERD_SERVICE_ID, self._dns_domain)
        records_PTR = self._ask_for_record(PTR_name, dpkt.dns.DNS_PTR)
        if not records_PTR:
            return False
        # Great, we know the PTR, make sure that we can also get the SRV and
        # TXT entries.
        TXT_name = SRV_name = records_PTR[0].data
        records_SRV = self._ask_for_record(SRV_name, dpkt.dns.DNS_SRV)
        # Check that SRV exists, and contains the expected hostname.
        if not records_SRV:
            return False
        if records_SRV[0].data[0] != hostname:
            raise error.TestFail('Unexpect SRV record: %r' % records_SRV[0])
        # TXT should exist.
        records_TXT = self._ask_for_record(TXT_name, dpkt.dns.DNS_TXT)
        if not records_TXT:
            return False
        # Labels in the TXT record should be 1:1 with our service info.
        txt_entries = records_TXT[0].data
        expected_entries = self.PEERD_SERVICE_INFO.copy()
        for entry in txt_entries:
            # All labels should be key/value pairs.
            if entry.find('=') < 0:
                raise error.TestFail('Unexpected TXT entry: %s' % entry)
            k, v = entry.split('=', 1)
            if k not in expected_entries or expected_entries[k] != v:
                raise error.TestFail('Unexpected TXT entry: %s' % entry)
            expected_entries.pop(k)
        if expected_entries:
            raise error.TestFail('Missing entries from TXT: %r' %
                                 expected_entries)
        return True


    def run_once(self):
        # Tell peerd about this exciting new service we have.
        service_token = self._peerd.expose_service(self.PEERD_SERVICE_ID,
                                                   self.PEERD_SERVICE_INFO)
        # Wait for advertisements of that service to appear from avahi.
        logging.info('Waiting to receive mDNS advertisements of '
                     'peerd services.')
        success, duration = self._host.run_until(self._found_desired_records,
                                                 self.TEST_TIMEOUT_SECONDS)
        if not success:
            raise error.TestFail('Did not receive mDNS advertisements in time.')
