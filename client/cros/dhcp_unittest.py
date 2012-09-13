#!/usr/bin/python

# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import socket
import sys
import time

from autotest_lib.client.cros import dhcp_handling_rule
from autotest_lib.client.cros import dhcp_packet
from autotest_lib.client.cros import dhcp_test_server

TEST_DATA_PATH_PREFIX = "client/cros/dhcp_test_data/"

def bin2hex(byte_str, justification=20):
    """
    Turn big hex strings into prettier strings of hex bytes.  Group those hex
    bytes into lines justification bytes long.
    """
    chars = ["x" + (hex(ord(c))[2:].zfill(2)) for c in byte_str]
    groups = []
    for i in xrange(0, len(chars), justification):
        groups.append("".join(chars[i:i+justification]))
    return "\n".join(groups)

def test_packet_serialization():
    log_file = open(TEST_DATA_PATH_PREFIX + "dhcp_discovery.log", "rb")
    binary_discovery_packet = log_file.read()
    log_file.close()
    discovery_packet = dhcp_packet.DhcpPacket(byte_str=binary_discovery_packet)
    if not discovery_packet.is_valid:
        return False
    generated_string = discovery_packet.to_binary_string()
    if generated_string is None:
        print "Failed to generate string from packet object."
        return False
    if generated_string != binary_discovery_packet:
        print "Packets didn't match: "
        print "Generated: \n%s" % bin2hex(generated_string)
        print "Expected: \n%s" % bin2hex(binary_discovery_packet)
        return False
    print "test_packet_serialization PASSED"
    return True

def receive_packet(a_socket, timeout_seconds=1.0):
    data = None
    start_time = time.time()
    while data is None and start_time + timeout_seconds > time.time():
        try:
            data, _ = a_socket.recvfrom(1024)
        except socket.timeout:
            pass # We expect many timeouts.
    if data is None:
        print "Timed out before we received a response from the server."
        return None

    print "Client received a packet of length %d from the server." % len(data)
    packet = dhcp_packet.DhcpPacket(byte_str=data)
    if not packet.is_valid:
        print "Received an invalid response from DHCP server."
        return None

    return packet

def test_simple_server_exchange(server):
    intended_ip = "127.0.0.42"
    server_ip = "127.0.0.1"
    lease_time_seconds = 60
    test_timeout = 3.0
    mac_addr = "\x01\x02\x03\x04\x05\x06"
    # Build up our packets.
    discovery_message = dhcp_packet.DhcpPacket.create_discovery_packet(mac_addr)
    request_message = dhcp_packet.DhcpPacket.create_request_packet(
            discovery_message.transaction_id,
            mac_addr,
            intended_ip,
            server_ip)
    # Build up the handling rules for the server and start the test.
    rules = []
    rules.append(dhcp_handling_rule.DhcpHandlingRule_RespondToDiscovery(
            intended_ip,
            server_ip,
            lease_time_seconds))
    rules.append(dhcp_handling_rule.DhcpHandlingRule_RespondToRequest(
            intended_ip,
            server_ip,
            lease_time_seconds))
    rules[-1].is_final_handler = True
    server.start_test(rules, test_timeout)
    # Because we don't want to require root permissions to run these tests,
    # listen on the loopback device, don't broadcast, and don't use reserved
    # ports (like the actual DHCP ports).  Use 8068/8067 instead.
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.bind(("127.0.0.1", 8068))
    client_socket.settimeout(0.1)
    client_socket.sendto(discovery_message.to_binary_string(),
                         (server_ip, 8067))

    offer_packet = receive_packet(client_socket)
    if offer_packet is None:
        return False

    if (offer_packet.message_type !=
        dhcp_packet.OPTION_VALUE_DHCP_MESSAGE_TYPE_OFFER):
        print "Type of DHCP response is not offer."
        return False

    if (offer_packet.get_field(dhcp_packet.FIELD_YOUR_IP) !=
        socket.inet_aton(intended_ip)):
        print "Server didn't offer the IP we expected."
        return False

    print "Offer looks good to the client, sending request."
    client_socket.sendto(request_message.to_binary_string(),
                         (server_ip, 8067))
    ack_packet = receive_packet(client_socket)
    if ack_packet is None:
        return False

    if (ack_packet.message_type !=
        dhcp_packet.OPTION_VALUE_DHCP_MESSAGE_TYPE_ACK):
        print "Type of DHCP response is not acknowledgement."
        return False

    if (offer_packet.get_field(dhcp_packet.FIELD_YOUR_IP) !=
        socket.inet_aton(intended_ip)):
        print "Server didn't give us the IP we expected."
        return False

    print "Waiting for the server to finish."
    server.wait_for_test_to_finish()
    print "Server agrees that the test is over."
    if not server.last_test_passed:
        print "Server is unhappy with the test result."
        return False

    print "test_simple_server_exchange PASSED."
    return True

def test_server_dialogue():
    server = dhcp_test_server.DhcpTestServer(ingress_address="127.0.0.1",
                                             ingress_port=8067,
                                             broadcast_address="127.0.0.1",
                                             broadcast_port=8068)
    server.start()
    ret = False
    if server.is_healthy:
        ret = test_simple_server_exchange(server)
    else:
        print "Server isn't healthy, aborting."
    print "Sending server stop() signal."
    server.stop()
    print "Stop signal sent."
    return ret

def run_tests():
    logger = logging.getLogger("dhcp")
    logger.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    logger.addHandler(stream_handler)
    retval = test_packet_serialization()
    retval &= test_server_dialogue()
    if retval:
        print "All tests PASSED."
        return 0
    else:
        print "Some tests FAILED"
        return -1

if __name__ == "__main__":
    sys.exit(run_tests())
