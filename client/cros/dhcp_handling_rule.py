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
    def __init__(self):
        super(DhcpHandlingRule, self).__init__()
        self._is_final_handler = False
        self._logger = logging.getLogger("dhcp.handling_rule")

    @property
    def logger(self):
        return self._logger

    @property
    def is_final_handler(self):
        return self._is_final_handler

    @is_final_handler.setter
    def is_final_handler(self, value):
        self._is_final_handler = value


    # Override this with your subclass, or all your tests will fail.  The
    # assumption is that the packet passed to this method is a valid DHCP
    # packet, but not necessarily any particular kind of DHCP packet.
    def handle(self, packet):
        return (RESPONSE_FAIL, ACTION_KEEP_HANDLER)

    # Override this if you will ever return RESPONSE_RESPOND_* in handle()
    # above.
    def respond(self, packet):
        return None

class DhcpHandlingRule_RespondToDiscovery(DhcpHandlingRule):
    def __init__(self,
                 intended_ip,
                 subnet_mask,
                 server_ip,
                 lease_time_seconds):
        super(DhcpHandlingRule_RespondToDiscovery, self).__init__()
        self._intended_ip = intended_ip
        self._subnet_mask = subnet_mask
        self._server_ip = server_ip
        self._lease_time_seconds = lease_time_seconds

    def handle(self, packet):
        if (packet.message_type !=
            dhcp_packet.OPTION_VALUE_DHCP_MESSAGE_TYPE_DISCOVERY):
            self.logger.info("Packet type was not DISCOVERY.  Ignoring.")
            return (RESPONSE_IGNORE, ACTION_KEEP_HANDLER)
        self.logger.info("Received valid DISCOVERY packet.  Processing.")
        action = ACTION_POP_HANDLER
        response = RESPONSE_RESPOND
        if self.is_final_handler:
            response = RESPONSE_RESPOND_SUCCESS
        return (response, action)

    def respond(self, packet):
        if (packet.message_type !=
            dhcp_packet.OPTION_VALUE_DHCP_MESSAGE_TYPE_DISCOVERY):
            self.logger.error("Server erroneously asked for a response to an "
                               "invalid packet.")
            return None
        self.logger.info("Responding to DISCOVERY packet.")
        packet = dhcp_packet.DhcpPacket.create_offer_packet(
                packet.transaction_id,
                packet.client_hw_address,
                self._intended_ip,
                self._subnet_mask,
                self._server_ip,
                self._lease_time_seconds)
        return packet
