# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import dhcp_handling_rule
from autotest_lib.client.cros import dhcp_packet
from autotest_lib.client.cros import dhcp_test_base

# Length of time the lease from the DHCP server is valid.
LEASE_TIME_SECONDS = 3600
# We'll fill in the subnet and give this address to the client.
INTENDED_IP_SUFFIX = "0.0.0.101"

class network_DhcpNak(dhcp_test_base.DhcpTestBase):
    """
    Tests a DHCP client's handling of NAK messages.

    Negotiates a lease, and then tests how the DHCP client processes
    NAKs in two scenarios. In the first scenario, the DHCP client
    is started anew, but with the cached lease on disk. In the
    second scenario, an already-running DHCP client is asked to
    renew its lease.

    In both scenarios, the NAK messages omit the DHCP server-id
    option. This is to emulate some DHCP servers (e.g. OpenBSD 4.6),
    which omit the DHCP server-id in NAK messages.
    """

    def common_setup(self):
        """
        Run common setup steps.
        """
        subnet_mask = self.ethernet_pair.interface_subnet_mask
        self.intended_ip = dhcp_test_base.DhcpTestBase.rewrite_ip_suffix(
            subnet_mask, self.server_ip, INTENDED_IP_SUFFIX)
        self.interface_name = self.ethernet_pair.peer_interface_name
        self.dhcp_options = {
            dhcp_packet.OPTION_SERVER_ID : self.server_ip,
            dhcp_packet.OPTION_SUBNET_MASK : subnet_mask,
            dhcp_packet.OPTION_IP_LEASE_TIME : LEASE_TIME_SECONDS,
            dhcp_packet.OPTION_REQUESTED_IP : self.intended_ip,
            dhcp_packet.OPTION_DNS_SERVERS : [],
            dhcp_packet.OPTION_DOMAIN_NAME : '',
            dhcp_packet.OPTION_DNS_DOMAIN_SEARCH_LIST : [],
            }
        self.negotiate_and_check_lease(self.dhcp_options)

    def reconnect_service(self):
        """
        Disconnect and reconnect Ethernet.

        Ask shill to disconnect and reconnect the Service for our
        virtual Ethernet link. This causes shill to shut down and
        restart dhcpcd for the link.
        """
        service = self.find_ethernet_service(self.interface_name)
        service.Disconnect()
        rules = [
            # Respond to DISCOVERY, but then NAK the REQUEST.
            dhcp_handling_rule.DhcpHandlingRule_RespondToDiscovery(
                self.intended_ip, self.server_ip, self.dhcp_options, {}),
            dhcp_handling_rule.DhcpHandlingRule_RejectRequest(),

            # Allow a successful negotiation the second time around.
            dhcp_handling_rule.DhcpHandlingRule_RespondToDiscovery(
                self.intended_ip, self.server_ip, self.dhcp_options, {}),
            dhcp_handling_rule.DhcpHandlingRule_RespondToRequest(
                self.intended_ip, self.server_ip, self.dhcp_options, {}),
            ]
        rules[-1].is_final_handler = True
        self.server.start_test(
            rules, dhcp_test_base.DHCP_NEGOTIATION_TIMEOUT_SECONDS)
        service.Connect()

    def force_dhcp_renew(self):
        """
        Force a DHCP renewal.

        Ask shill to Refresh the configuration for the IPConfig object
        associated with our virtual Ethernet link. This causes shill
        to ask dhcpcd to renew its DHCP lease.
        """
        rules = [
            # Reject REQUEST from renewal attempt.
            dhcp_handling_rule.DhcpHandlingRule_RejectRequest(),

            # Allow a successful negotiation after that.
            dhcp_handling_rule.DhcpHandlingRule_RespondToDiscovery(
                self.intended_ip, self.server_ip, self.dhcp_options, {}),
            dhcp_handling_rule.DhcpHandlingRule_RespondToRequest(
                self.intended_ip, self.server_ip, self.dhcp_options, {}),
            ]
        rules[-1].is_final_handler = True
        self.server.start_test(
            rules, dhcp_test_base.DHCP_NEGOTIATION_TIMEOUT_SECONDS)
        self.get_interface_ipconfig_objects(self.interface_name)[0].Refresh()

    def send_both_nak_and_ack(self, is_nak_before_ack):
        """
        Send both a NAK and an ACK on re-connect to Ethernet.

        Ask shill to disconnect and reconnect the Service for our
        virtual Ethernet link. This causes shill to shut down and
        restart dhcpcd for the link.  Then perform a test where
        the server responds to a REQUEST with both a NAK and an ACK.

        @param is_nak_before_ack bool whether the NAK should be sent
             before the ACK, otherwise vice-versa.
        """
        service = self.find_ethernet_service(self.interface_name)
        service.Disconnect()
        rules = [
            # Respond to DISCOVERY, but then both NAK and ACK the REQUEST.
            dhcp_handling_rule.DhcpHandlingRule_RespondToDiscovery(
                self.intended_ip, self.server_ip, self.dhcp_options, {}),
            dhcp_handling_rule.DhcpHandlingRule_RejectAndRespondToRequest(
                self.intended_ip, self.server_ip, self.dhcp_options, {},
                is_nak_before_ack),
            ]
        rules[-1].is_final_handler = True
        self.server.start_test(
            rules, dhcp_test_base.DHCP_NEGOTIATION_TIMEOUT_SECONDS)
        service.Connect()

    def send_nak_then_ack(self):
        """ Respond with a NAK, then with an ACK. """
        self.send_both_nak_and_ack(True)

    def send_ack_then_nak(self):
        """ Respond with a ACK, then with an NAK. """
        self.send_both_nak_and_ack(False)

    def test_body(self):
        """
        Entry point for this test.

        This is called from DhcpTestBase.run_once().
        """
        self.common_setup()
        for sub_test in (self.reconnect_service,
                         self.force_dhcp_renew,
                         self.send_nak_then_ack,
                         self.send_ack_then_nak):
            sub_test()
            self.server.wait_for_test_to_finish()
            if not self.server.last_test_passed:
                raise error.TestFail('Test failed (%s): active rule is %s' % (
                        sub_test.__name__, self.server.current_rule))
