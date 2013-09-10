# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dpkt
import socket

from lansim import tools

class SimpleHost(object):
    """A simple host supporting IPv4.

    This class is useful as a base clase to implement other hosts. It supports
    a single IPv4 address.
    """
    def __init__(self, sim, hw_addr, ip_addr):
        """Creates the host and associates it with the given NetworkBridge.

        @param sim: The Simulator interface where this host lives.
        @param hw_addr: Hex or binary representation of the Ethernet address.
        @param ip_addr: The IPv4 address. For example: "10.0.0.1".
        """
        self._sim = sim
        self._hw_addr = hw_addr
        self._ip_addr = ip_addr
        self._bin_hw_addr = tools.inet_hwton(hw_addr)
        self._bin_ip_addr = socket.inet_aton(ip_addr)
        # Reply to broadcast ARP requests.
        rule = {
            "dst": "\xff" * 6, # Broadcast HW addr.
            "arp.pln": 4, # Protocol Addres Length is 4 (IP v4).
            "arp.op": dpkt.arp.ARP_OP_REQUEST,
            "arp.tpa": self._bin_ip_addr}
        sim.add_match(rule, self.arp_request)

        # Reply to unicast ARP requests.
        rule["dst"] = self._bin_hw_addr
        sim.add_match(rule, self.arp_request)

    def arp_request(self, pkt):
        """Sends the ARP_REPLY matching the request.

        @param pkt: a dpkt.Packet with the ARP_REQUEST.
        """
        arp_resp = dpkt.arp.ARP(
            op = dpkt.arp.ARP_OP_REPLY,
            pln = 4,
            tpa = pkt.arp.spa, # Target Protocol Address.
            tha = pkt.arp.sha, # Target Hardware Address.
            spa = self._bin_ip_addr, # Source Protocol Address.
            sha = self._bin_hw_addr) # Source Hardware Address.
        eth_resp = dpkt.ethernet.Ethernet(
            dst = pkt.arp.sha,
            src = self._bin_hw_addr,
            type = dpkt.ethernet.ETH_TYPE_ARP,
            data = arp_resp)
        self._sim.write(eth_resp)


