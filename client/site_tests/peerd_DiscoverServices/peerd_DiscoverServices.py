# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import chrooted_avahi
from autotest_lib.client.cros.netprotos import interface_host
from autotest_lib.client.cros.netprotos import zeroconf
from autotest_lib.client.cros.tendo import peerd_helper


class peerd_DiscoverServices(test.test):
    """Test that peerd can correctly discover services over mDNS."""
    version = 1

    FAKE_HOST_HOSTNAME = 'test-host'
    TEST_TIMEOUT_SECONDS = 30
    PEER_ID = '123e4567-e89b-12d3-a456-426655440000'
    PEER_SERBUS_VERSION = '1.12'
    PEER_NAME = 'A test device'
    PEER_NOTE = 'I am not a real device.'
    PEER_SERVICES = {
            'test-service-0': {'some_data': 'a value',
                               'other_data': 'another value'},
            'test-service-1': {'again': 'so much data'},
    }
    SERBUS_SERVICE_NAME = '_serbus'
    SERBUS_PROTOCOL = '_tcp'
    SERBUS_PORT = 0
    SERBUS_TXT_DICT = {'ver': PEER_SERBUS_VERSION,
                       'id': PEER_ID,
                       'name': PEER_NAME,
                       'note': PEER_NOTE,
                       'services': '.'.join(PEER_SERVICES.iterkeys())}
    UNIQUE_PREFIX = 'a_unique_mdns_prefix'



    def initialize(self):
        # Make sure these are initiallized to None in case we throw
        # during self.initialize().
        self._chrooted_avahi = None
        self._peerd = None
        self._host = None
        self._zc_listener = None
        self._chrooted_avahi = chrooted_avahi.ChrootedAvahi()
        self._chrooted_avahi.start()
        # Start up a fresh copy of peerd with really verbose logging.
        self._peerd = peerd_helper.make_helper(verbosity_level=3)
        # Listen on our half of the interface pair for mDNS advertisements.
        self._host = interface_host.InterfaceHost(
                self._chrooted_avahi.unchrooted_interface_name)
        self._zc_listener = zeroconf.ZeroconfDaemon(self._host,
                                                    self.FAKE_HOST_HOSTNAME)
        # The queries for hostname/dns_domain are IPCs and therefore relatively
        # expensive.  Do them just once.
        hostname = self._chrooted_avahi.hostname
        dns_domain = self._chrooted_avahi.dns_domain
        if not hostname or not dns_domain:
            raise error.TestFail('Failed to get hostname/domain from avahi.')
        self._dns_domain = dns_domain
        self._hostname = '%s.%s' % (hostname, dns_domain)


    def cleanup(self):
        for obj in (self._chrooted_avahi,
                    self._host,
                    self._peerd):
            if obj is not None:
                obj.close()


    def _has_expected_peer(self):
        peer = self._peerd.has_peer(self.PEER_ID,
                                    name=self.PEER_NAME,
                                    note=self.PEER_NOTE)
        if peer is None:
            logging.debug('No peer found.')
            return False
        logging.debug('Found peer=%s', peer)
        if len(peer.services) != len(self.PEER_SERVICES):
            logging.debug('Found %d services, but expected %d.',
                          len(peer.services), len(self.PEER_SERVICES))
            return False
        for service_id, info in self.PEER_SERVICES.iteritems():
            service = None
            for s in peer.services:
                if s.service_id == service_id:
                    service = s
                    break
            else:
                logging.debug('No service %s found.', service_id)
                return False
            if service.service_info != info:
                logging.debug('Invalid info found for service %s, '
                              'expected %r but got %r.', service_id,
                              info, service.service_info)
                return False
        return True


    def run_once(self):
        # Expose serbus mDNS records through our fake peer.
        self._zc_listener.register_service(
                self.UNIQUE_PREFIX,
                self.SERBUS_SERVICE_NAME,
                self.SERBUS_PROTOCOL,
                self.SERBUS_PORT,
                ['='.join(pair) for pair in self.SERBUS_TXT_DICT.iteritems()])
        for service_id, info in self.PEER_SERVICES.iteritems():
            self._zc_listener.register_service(
                    self.UNIQUE_PREFIX,
                    '_' + service_id,
                    self.SERBUS_PROTOCOL,
                    self.SERBUS_PORT,
                    ['='.join(pair) for pair in info.iteritems()])

        # Look for mDNS records through peerd
        self._peerd.start_monitoring([peerd_helper.TECHNOLOGY_MDNS])
        # Wait for advertisements of that service to appear from avahi.
        logging.info('Waiting for peerd to discover our services.')
        success, duration = self._host.run_until(self._has_expected_peer,
                                                 self.TEST_TIMEOUT_SECONDS)
        logging.debug('Took %f seconds to find our peer.', duration)
        if not success:
            raise error.TestFail('Did not receive mDNS advertisements in time.')
