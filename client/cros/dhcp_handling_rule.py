# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
DHCP handling rules are ways to record expectations for a DhcpTestServer.

When a handling rule reaches the front of the DhcpTestServer handling rule
queue, the server begins to ask the rule what it should do with each incoming
DHCP packet (in the form of a DhcpPacket).  The handle method is expected to
return a tuple (response, action) where response indicates whether the packet
should be ignored or responded to and whether the test failed, succeeded, or is
continuing.  The action part of the tuple refers to whether or not the rule
should be be removed from the test server's handling rule queue.
"""

import logging

from autotest_lib.client.cros import dhcp_packet

RESPONSE_FAIL = 0
RESPONSE_IGNORE = 1
RESPONSE_IGNORE_SUCCESS = 3
RESPONSE_RESPOND = 2
RESPONSE_RESPOND_SUCCESS = 4

ACTION_POP_HANDLER = 0
ACTION_KEEP_HANDLER = 1

class DhcpHandlingRule(object):
    """
    DhcpHandlingRule defines an interface between the DhcpTestServer and
    subclasses of DhcpHandlingRule.  A handling rule at the front of the
    DhcpTestServer rule queue is first asked what should be done with a packet
    via handle().  Handle returns a tuple as described above.  If the response
    from handle() indicates that a packet should be sent in response, the server
    asks the handling rule to construct a response packet via respond().
    """
    def __init__(self, additional_options):
        """
        |additional_options| should be a dictionary that maps from
        dhcp_packet.OPTION_* to values.  For instance:

        {dhcp_packet.OPTION_SERVER_ID : "10.10.10.1"}

        These options are injected into response packets if the client requests
        it.  See inject_options().
        """
        super(DhcpHandlingRule, self).__init__()
        self._is_final_handler = False
        self._logger = logging.getLogger("dhcp.handling_rule")
        self._options = additional_options

    @property
    def logger(self):
        return self._logger

    @property
    def is_final_handler(self):
        return self._is_final_handler

    @is_final_handler.setter
    def is_final_handler(self, value):
        self._is_final_handler = value

    @property
    def options(self):
        """
        Returns a dictionary that maps from DhcpPacket options to their values.
        """
        return self._options

    def handle(self, packet):
        """
        The DhcpTestServer will call this method to ask a handling rule whether
        it wants to take some action in response to a packet.

        |packet| is a valid DHCP packet, but the values of fields and presence
        of options is not guaranteed.
        """
        return (RESPONSE_FAIL, ACTION_KEEP_HANDLER)

    def respond(self, query_packet):
        """
        The DhcpTestServer will call this method if the DhcpHandlingRule signals
        that it wishes to respond to a packet above.  |query_packet| is the same
        packet passed to handle().
        """
        return None

    def inject_options(self, packet, requested_parameters):
        """
        Adds options listed in the intersection of |requested_parameters| and
        |self.options| to |packet|.

        |packet| is a DhcpPacket.

        |requested_parameters| is a list of options numbers as you would find in
        a DHCP_DISCOVER or DHCP_REQUEST packet after being parsed by DhcpPacket
        (e.g. [1, 121, 33, 3, 6, 12]).

        Subclassed handling rules may call this to inject options into response
        packets to the client.  This process emulates a real DHCP server which
        would have a pool of configuration settings to hand out to DHCP clients
        upon request.
        """
        for option, value in self.options.items():
            if option.number in requested_parameters:
                packet.set_option(option, value)


class DhcpHandlingRule_RespondToDiscovery(DhcpHandlingRule):
    """
    This handler will accept any DISCOVER packet received by the server. In
    response to such a packet, the handler will construct an OFFER packet
    offering |intended_ip| from a server at |server_ip| (from the constructor).
    """
    def __init__(self,
                 intended_ip,
                 server_ip,
                 additional_options):
        """
        |intended_ip| is an IPv4 address string like "192.168.1.100".

        |server_ip| is an IPv4 address string like "192.168.1.1".

        |additional_options| is handled as explained by DhcpHandlingRule.
        """
        super(DhcpHandlingRule_RespondToDiscovery, self).__init__(
                additional_options)
        self._intended_ip = intended_ip
        self._server_ip = server_ip

    def handle(self, query_packet):
        if (query_packet.message_type !=
            dhcp_packet.OPTION_VALUE_DHCP_MESSAGE_TYPE_DISCOVERY):
            self.logger.info("Packet type was not DISCOVERY.  Ignoring.")
            return (RESPONSE_IGNORE, ACTION_KEEP_HANDLER)
        self.logger.info("Received valid DISCOVERY packet.  Processing.")
        action = ACTION_POP_HANDLER
        response = RESPONSE_RESPOND
        if self.is_final_handler:
            response = RESPONSE_RESPOND_SUCCESS
        return (response, action)

    def respond(self, query_packet):
        if (query_packet.message_type !=
            dhcp_packet.OPTION_VALUE_DHCP_MESSAGE_TYPE_DISCOVERY):
            self.logger.error("Server erroneously asked for a response to an "
                               "invalid packet.")
            return None
        self.logger.info("Responding to DISCOVERY packet.")
        response_packet = dhcp_packet.DhcpPacket.create_offer_packet(
                query_packet.transaction_id,
                query_packet.client_hw_address,
                self._intended_ip,
                self._server_ip)
        requested_parameters = query_packet.get_option(
                dhcp_packet.OPTION_PARAMETER_REQUEST_LIST)
        if requested_parameters is not None:
            self.inject_options(response_packet, requested_parameters)
        return response_packet


class DhcpHandlingRule_RespondToRequest(DhcpHandlingRule):
    """
    This handler accepts any REQUEST packet that contains options for
    SERVER_ID and REQUESTED_IP that match |expected_server_ip| and
    |expected_requested_ip| respectively.  It responds with an ACKNOWLEDGEMENT
    packet from a DHCP server at |server_ip| granting |granted_ip| to a client
    at the address given in the REQUEST packet.
    """
    def __init__(self,
                 expected_requested_ip,
                 expected_server_ip,
                 additional_options,
                 server_ip=None,
                 granted_ip=None):
        """
        All *_ip arguments are IPv4 address strings like "192.168.1.101".

        |additional_options| is handled as explained by DhcpHandlingRule.
        """
        super(DhcpHandlingRule_RespondToRequest, self).__init__(
                additional_options)
        self._expected_requested_ip = expected_requested_ip
        self._expected_server_ip = expected_server_ip
        # Default the granted IP and server IP to the expected values from the
        # client, unless explicitly specified otherwise
        self._granted_ip = granted_ip
        if granted_ip is None:
            self._granted_ip = self._expected_requested_ip
        self._server_ip = server_ip
        if self._server_ip is None:
            self._server_ip = self._expected_server_ip

    def handle(self, query_packet):
        if (query_packet.message_type !=
            dhcp_packet.OPTION_VALUE_DHCP_MESSAGE_TYPE_REQUEST):
            self.logger.info("Packet type was not REQUEST, ignoring.")
            return (RESPONSE_IGNORE, ACTION_KEEP_HANDLER)

        self.logger.info("Received REQUEST packet, checking fields...")
        server_ip = query_packet.get_option(dhcp_packet.OPTION_SERVER_ID)
        requested_ip = query_packet.get_option(dhcp_packet.OPTION_REQUESTED_IP)
        if (server_ip is None) or (requested_ip is None):
            self.logger.info("REQUEST packet did not have the expected "
                             "options, discarding.")
            return (RESPONSE_IGNORE, ACTION_KEEP_HANDLER)

        if server_ip != self._expected_server_ip:
            self.logger.warning("REQUEST packet's server ip did not match our "
                                "expectations; expected %s but got %s" %
                                (self._expected_server_ip, server_ip))
            return (RESPONSE_IGNORE, ACTION_KEEP_HANDLER)

        if requested_ip != self._expected_requested_ip:
            self.logger.warning("REQUEST packet's requested IP did not match "
                                "our expectations; expected %s but got %s" %
                                (self._expected_requested_ip, requested_ip))
            return (RESPONSE_IGNORE, ACTION_KEEP_HANDLER)

        self.logger.info("Received valid REQUEST packet, processing")
        action = ACTION_POP_HANDLER
        response = RESPONSE_RESPOND
        if self.is_final_handler:
            response = RESPONSE_RESPOND_SUCCESS
        return (response, action)

    def respond(self, query_packet):
        if (query_packet.message_type !=
            dhcp_packet.OPTION_VALUE_DHCP_MESSAGE_TYPE_REQUEST):
            self.logger.error("Server erroneously asked for a response to an "
                              "invalid packet.")
            return None

        self.logger.info("Responding to REQUEST packet.")
        response_packet = dhcp_packet.DhcpPacket.create_acknowledgement_packet(
                query_packet.transaction_id,
                query_packet.client_hw_address,
                self._granted_ip,
                self._server_ip)
        requested_parameters = query_packet.get_option(
                dhcp_packet.OPTION_PARAMETER_REQUEST_LIST)
        if requested_parameters is not None:
            self.inject_options(response_packet, requested_parameters)
        return response_packet
