# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.cros import dhcp_packet
from autotest_lib.client.cros import dhcp_test_base
from autotest_lib.client.cros import radvd_server
from autotest_lib.client.cros.networking import shill_proxy

# Length of time the lease from the DHCP server is valid.
LEASE_TIME_SECONDS = 60
# We'll fill in the subnet and give this address to the client.
INTENDED_IP_SUFFIX = '0.0.0.101'

class network_Ipv6SimpleNegotiation(dhcp_test_base.DhcpTestBase):
    """
    The test subclass that implements IPv6 negotiation.  This test
    starts an IPv6 router, then completes a normal DHCP negotiation
    to bring up a stable connection.  It then performs a series of
    tests on the IPv6 addresses that the DUT should have also gained.
    """

    def _get_ip6_addresses(self):
        """Gets the list of client IPv6 addresses.

        Retrieve IPv6 addresses associated with the "client side" of the
        pseudo-interface pair.  Returns a dict keyed by the IPv6 address,
        with the values being the array of attribute strings that follow
        int the "ip addr show" output.  For example, a line containing:

            inet6 fe80::ae16:2dff:fe01:0203/64 scope link

        will turn into a dict key:

            'fe80::ae16:2dff:fe01:0203/64': [ 'scope', 'link' ]

        """
        addr_output = utils.system_output(
            "ip -6 addr show dev %s" % self.ethernet_pair.peer_interface_name)
        addresses = {}
        for line in addr_output.splitlines():
            parts = line.lstrip().split()
            if parts[0] != 'inet6' or 'deprecated' in parts:
                continue
            addresses[parts[1]] = parts[2:]
        return addresses


    def _get_link_address(self):
        """Get the client MAC address.

        Retrieve the MAC address associated with the "client side" of the
        pseudo-interface pair.  For example, the "ip link show" output:

            link/ether 01:02:03:04:05:05 brd ff:ff:ff:ff:ff:ff

        will cause a return of "01:02:03:04:05:05"

        """
        addr_output = utils.system_output(
            'ip link show %s' % self.ethernet_pair.peer_interface_name)
        for line in addr_output.splitlines():
            parts = line.lstrip().split(' ')
            if parts[0] == 'link/ether':
                return parts[1]


    def negotiate_dhcp_lease(self):
        """Perform a DHCP negotiation.

        Although this test isn't really meant to validate DHCP negotiation,
        we should go through this process so the connection manager keeps the
        interface up long enough for the IPv6 negotiation to complete reliably.

        """
        subnet_mask = self.ethernet_pair.interface_subnet_mask
        intended_ip = dhcp_test_base.DhcpTestBase.rewrite_ip_suffix(
                subnet_mask,
                self.server_ip,
                INTENDED_IP_SUFFIX)
        # Two real name servers, and a bogus one to be unpredictable.
        dns_servers = ['8.8.8.8', '8.8.4.4', '192.168.87.88']
        domain_name = 'corp.google.com'
        dns_search_list = [
                'you.can.pry.google.com',
                'my.pixel.google.com',
                'from.my.cold.dead.hands.google.com',
                ]
        # This is the pool of information the server will give out to the client
        # upon request.
        dhcp_options = {
                dhcp_packet.OPTION_SERVER_ID : self.server_ip,
                dhcp_packet.OPTION_SUBNET_MASK : subnet_mask,
                dhcp_packet.OPTION_IP_LEASE_TIME : LEASE_TIME_SECONDS,
                dhcp_packet.OPTION_REQUESTED_IP : intended_ip,
                dhcp_packet.OPTION_DNS_SERVERS : dns_servers,
                dhcp_packet.OPTION_DOMAIN_NAME : domain_name,
                dhcp_packet.OPTION_DNS_DOMAIN_SEARCH_LIST : dns_search_list,
                }
        self.negotiate_and_check_lease(dhcp_options)


    def verify_ipv6_addresses(self):
        """Verify IPv6 configuration.

        Perform various tests to validate the IPv6 addresses acquired by
        the client.

        """
        addresses = self._get_ip6_addresses()
        logging.info('Got addresses %r', addresses)
        global_addresses = [key for key in addresses
                            if 'global' in addresses[key]]

        if len(global_addresses) != 2:
            raise error.TestError('Expected 2 global address but got %d' %
                                  len(global_addresses))

        prefix = radvd_server.RADVD_DEFAULT_PREFIX
        prefix = prefix[:prefix.index('::')]
        for address in global_addresses:
            if not address.startswith(prefix):
                raise error.TestError('Global address %s does not start with '
                                      'expected prefix %s' %
                                      address, prefix)

        # One globally scoped address should be based on the last 3 octets
        # of the MAC adddress, while the other should not.  For example,
        # for MAC address "01:02:03:04:05:06", we should see an address
        # that ends with "4:506/64" (the "/64" is the default radvd suffix).
        link_parts = [int(b, 16) for b in self._get_link_address().split(':')]
        address_suffix = '%x:%x%s' % (link_parts[3],
                                      (link_parts[4] << 8) | link_parts[5],
                                      radvd_server.RADVD_DEFAULT_SUFFIX)
        mac_related_addresses = [addr for addr in global_addresses
                                 if addr.endswith(address_suffix)]
        if len(mac_related_addresses) != 1:
            raise error.TestError('Expected 1 mac-related global address but '
                                  'got %d' % len(mac_related_addresses))
        mac_related_address = mac_related_addresses[0]

        local_address_count = len(addresses) - len(global_addresses)
        if local_address_count <= 0:
            raise error.TestError('Expected at least 1 non-global address but '
                                  'got %d' % local_address_count)

        temporary_address = [addr for addr in global_addresses
                                 if addr != mac_related_address][0]
        self.verify_ipconfig_contains(temporary_address)


    def verify_ipconfig_contains(self, address_and_prefix):
        """Verify that shill has an IPConfig entry with the specified address.

        @param address_and_prefix string with address/prefix to search for.

        """
        address, prefix_str = address_and_prefix.split('/')
        prefix = int(prefix_str)
        for ipconfig in self.get_interface_ipconfig_objects(
                self.ethernet_pair.peer_interface_name):
            ipconfig_properties = shill_proxy.ShillProxy.dbus2primitive(
                    ipconfig.GetProperties(utf8_strings=True))
            if 'Method' not in ipconfig_properties:
                continue

            if ipconfig_properties['Method'] != 'ipv6':
                continue

            break

        else:
            raise error.TestError('Found no IPv6 IPConfig entries')

        for property, value in (('Address', address), ('Prefixlen', prefix)):
            if property not in ipconfig_properties:
               raise error.TestError('IPv6 IPConfig entry does not '
                                     'contain property %s' % property)
            if ipconfig_properties[property] != value:
               raise error.TestError('IPv6 IPConfig property %s does not '
                                     'contain the expected value %s; '
                                     'instead it is %s' %
                                     (property, value,
                                      ipconfig_properties[property]))


    def test_body(self):
        """The main body for this test."""
        server = radvd_server.RadvdServer(self.ethernet_pair.interface_name)
        server.start_server()

        try:
            self.negotiate_dhcp_lease()

            # Wait a bit more for IPv6 negotiation to complete.
            time.sleep(radvd_server.RADVD_DEFAULT_MAX_ADV_INTERVAL)

            # In this time, we should have also acquired an IPv6 address.
            self.verify_ipv6_addresses()

        finally:
            server.stop_server()
