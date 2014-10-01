# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dpkt
import logging

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import chrooted_avahi
from autotest_lib.client.cros.netprotos import interface_host
from autotest_lib.client.cros.netprotos import zeroconf
from autotest_lib.client.cros.tendo import peerd_helper


class peerd_AdvertiseServices(test.test):
    """Test that peerd can correctly advertise services over mDNS."""
    version = 1

    ANY_VALUE = object()  # Use reference equality for wildcard.
    FAKE_HOST_HOSTNAME = 'test-host'
    TEST_TIMEOUT_SECONDS = 30
    TEST_SERVICE_ID = 'test-service-0'
    TEST_SERVICE_INFO = {'some_data': 'a value',
                          'other_data': 'another value'}
    SERBUS_SERVICE_ID = 'serbus'
    SERBUS_SERVICE_INFO = {'ver': '1.0',
                           'id': ANY_VALUE,
                           'note': ANY_VALUE,
                           'name': ANY_VALUE,
                           'services': TEST_SERVICE_ID}


    def initialize(self):
        # Make sure these are initiallized to None in case we throw
        # during self.initialize().
        self._chrooted_avahi = None
        self._peerd = None
        self._host = None
        self._zc_listener = None
        self._chrooted_avahi = chrooted_avahi.ChrootedAvahi()
        self._chrooted_avahi.start()
        # Start up a cleaned up peerd with really verbose logging.
        self._peerd = peerd_helper.make_helper(start_instance=True,
                                               verbosity_level=3)
        # Listen on our half of the interface pair for mDNS advertisements.
        self._host = interface_host.InterfaceHost(
                self._chrooted_avahi.unchrooted_interface_name)
        self._zc_listener = zeroconf.ZeroconfDaemon(self._host,
                                                    self.FAKE_HOST_HOSTNAME)
        # The queries for hostname/dns_domain are IPCs and therefor relatively
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


    def _check_txt_record_data(self, expected_data, actual_data):
        # Labels in the TXT record should be 1:1 with our service info.
        expected_entries = expected_data.copy()
        for entry in actual_data:
            # All labels should be key/value pairs.
            if entry.find('=') < 0:
                raise error.TestFail('Unexpected TXT entry: %s' % entry)
            k, v = entry.split('=', 1)
            if k not in expected_entries:
                raise error.TestFail('Unexpected TXT entry key: %s' % k)
            if (expected_entries[k] != self.ANY_VALUE and
                    expected_entries[k] != v):
                raise error.TestFail('Expected TXT value=%s for entry=%s '
                                     'but got value=%r instead.' %
                                     (expected_entries[k], k, v))
            expected_entries.pop(k)
        if expected_entries:
            # Raise a detailed exception here, rather than return false.
            raise error.TestFail('Missing entries from TXT: %r' %
                                 expected_entries)
        return True


    def _ask_for_record(self, record_name, record_type, predicate):
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
            if not predicate(found_records[0].data):
                raise error.TestFail('Found record with name=%s and type=%r '
                                     'and unexpected value=%r.' %
                                     (record_name, record_type,
                                      found_records[0].data))
            logging.debug('Found record with name=%s, type=%r.',
                          record_name, record_type)
            return found_records[0]
        logging.debug('Did not see record with name=%s and type=%r',
                      record_name, record_type)
        desired_records = [(record_name, record_type)]
        self._zc_listener.send_request(desired_records)
        return None


    def _found_service_records(self, service_id, service_info):
        PTR_name = '_%s._tcp.%s' % (service_id, self._dns_domain)
        record_PTR = self._ask_for_record(PTR_name, dpkt.dns.DNS_PTR,
                                          lambda data: True)
        if not record_PTR:
            return False
        # Great, we know the PTR, make sure that we can also get the SRV and
        # TXT entries.
        TXT_name = SRV_name = record_PTR.data
        if not self._ask_for_record(SRV_name, dpkt.dns.DNS_SRV,
                                    lambda data: data[0] == self._hostname):
            return False
        # TXT should exist.
        record_TXT = self._ask_for_record(
                TXT_name, dpkt.dns.DNS_TXT,
                lambda data: self._check_txt_record_data(service_info, data))
        if not record_TXT:
            return False
        return True


    def _found_desired_records(self):
        """Verifies that avahi has all the records we care about.

        Asks the |self._zc_listener| for records we expect to correspond
        to our test service.  Will trigger queries if we don't find the
        expected records.

        @return True if we have all expected records, False otherwise.

        """
        logging.debug('Looking for records for %s.', self._hostname)
        # First, check that Avahi is doing the simple things and publishing
        # an A record.
        if not self._ask_for_record(
                self._hostname, dpkt.dns.DNS_A,
                lambda data: data == self._chrooted_avahi.avahi_interface_addr):
            return False
        logging.debug('Found A record, looking for serbus records.')
        # If we can see Avahi publishing that it's there, check that it has
        # appropriate entries for its serbus master record.
        if not self._found_service_records(self.SERBUS_SERVICE_ID,
                                           self.SERBUS_SERVICE_INFO):
            return False
        logging.debug('Found serbus records, looking for service records.')
        # We also expect the subservices we've added to exist.
        if not self._found_service_records(self.TEST_SERVICE_ID,
                                           self.TEST_SERVICE_INFO):
            return False
        logging.debug('Found all desired records.')
        return True


    def run_once(self):
        # Tell peerd about this exciting new service we have.
        service_token = self._peerd.expose_service(self.TEST_SERVICE_ID,
                                                   self.TEST_SERVICE_INFO)
        # Wait for advertisements of that service to appear from avahi.
        logging.info('Waiting to receive mDNS advertisements of '
                     'peerd services.')
        success, duration = self._host.run_until(self._found_desired_records,
                                                 self.TEST_TIMEOUT_SECONDS)
        if not success:
            raise error.TestFail('Did not receive mDNS advertisements in time.')
