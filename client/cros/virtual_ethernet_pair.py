# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
VirtualEthernetPair provides methods for setting up and tearing down a virtual
ethernet interface for use in tests.  You will probably need to be root on test
devices to use this class.  The constructor allows you to specify your IP's to
assign to both ends of the pair, however, if you wish to leave the interface
unconfigured, simply pass None.  You may also specify the subnet of your ip
addresses.  Failing to do so leaves them with default in ifconfig.

Example usage:
vif = virtual_ethernet_pair.VirtualEthernetPair(interface_prefix="veth_",
                                                interface_ip="192.168.177.1/24",
                                                peer_interface_ip=None)
vif.setup()
if not vif.is_healthy:
    # bad things happened while creating the interface
    # ... abort gracefully

interface_name = vif.interface_name
peer_interface_name = vif.peer_interface_name
#... do things with your interface

# You must call this if you want to leave the system in a good state.
vif.teardown()

Alternatively:

with virtual_ethernet_pair.VirtualEthernetPair(...) as vif:
    if not vif.is_healthy:
        # bad things happened while creating the interface
        # ... abort gracefully

    interface_name = vif.interface_name
    peer_interface_name = vif.peer_interface_name
    #... do things with your interface

"""

import logging
import socket
import struct

from autotest_lib.client.bin import utils

class VirtualEthernetPair(object):
    @staticmethod
    def _get_ip(interface_name):
        """
        Returns the IPv4 address for |interface_name| (e.g "192.168.1.1") if
        configured, and returns None if that address could not be found.
        """
        # "ipaddr show %s 2> /dev/null" returns something that looks like:
        #
        # 2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP qlen 1000
        #    link/ether ac:16:2d:07:51:0f brd ff:ff:ff:ff:ff:ff
        #    inet 172.22.73.124/22 brd 172.22.75.255 scope global eth0
        #    inet6 2620:0:1000:1b02:ae16:2dff:fe07:510f/64 scope global dynamic
        #       valid_lft 2591982sec preferred_lft 604782sec
        #    inet6 fe80::ae16:2dff:fe07:510f/64 scope link
        #       valid_lft forever preferred_lft forever
        #
        # Which we grep for 'inet ' to extract the third line, then sed to
        # extract just the substring "172.22.73.124".
        cmd_get_ip = ("ip addr show %s 2> /dev/null | grep 'inet ' | "
                      "sed -E 's/\\W+inet ([0-9]+(\\.[0-9]+){3}).*/\\1/'" %
                      interface_name)
        addr = utils.system_output(cmd_get_ip)
        if not addr:
            return None
        return addr

    @staticmethod
    def _interface_exists(interface_name):
        """
        Returns True iff we found an interface with name |interface_name|.
        """
        return utils.system("ifconfig %s &> /dev/null" % interface_name,
                            ignore_status=True) == 0

    @staticmethod
    def _get_subnet_prefix_size(interface_name):
        """
        Returns the number of bits in the IPv4 address prefix (e.g. 24) for
        |interface_name| if configured.  If not configured, returns None.
        """
        # "ipaddr show %s 2> /dev/null" returns something that looks like:
        #
        # 2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP qlen 1000
        #    link/ether ac:16:2d:07:51:0f brd ff:ff:ff:ff:ff:ff
        #    inet 172.22.73.124/22 brd 172.22.75.255 scope global eth0
        #    inet6 2620:0:1000:1b02:ae16:2dff:fe07:510f/64 scope global dynamic
        #       valid_lft 2591982sec preferred_lft 604782sec
        #    inet6 fe80::ae16:2dff:fe07:510f/64 scope link
        #       valid_lft forever preferred_lft forever
        #
        # Which we grep for 'inet ' to extract the third line, then sed to
        # extract just ip address's subnet size (e.g. /24).  We return just the
        # 24 as an integer.
        cmd_get_subnet = \
                ("ip addr show %s 2> /dev/null | grep 'inet ' | "
                 "sed -E "
                 "'s/\\W+inet ([0-9]+(\\.[0-9]+){3})\\/([0-9]+).*/\\3/'" %
                 interface_name)
        addr = utils.system_output(cmd_get_subnet)
        if not addr:
            return None
        return int(addr)

    @staticmethod
    def _get_subnet_mask(interface_name):
        """
        Returns the subnet mask (e.g. "255.255.255.0") for |interface_name|
        if configured.  If not configured, returns None.
        """
        prefix_size = \
                VirtualEthernetPair._get_subnet_prefix_size(interface_name)
        if prefix_size is None:
            # No prefix configured
            return None
        if prefix_size <= 0 or prefix_size >= 32:
            logging.error("Very oddly configured IP address with a /%d "
                          "prefix size" % prefix_size)
            return None
        all_ones = 0xffffffff
        int_mask = (all_ones << (32 - prefix_size)) & all_ones
        return socket.inet_ntoa(struct.pack("!I", int_mask))


    def __init__(self,
                 interface_name="veth_master",
                 peer_interface_name="veth_slave",
                 interface_ip="10.9.8.1/24",
                 peer_interface_ip="10.9.8.2/24"):
        """
        Construct a object managing a virtual ethernet pair.  One end of the
        interface will be called |interface_name|, and the peer end
        |peer_interface_name|.  You may get the interface names later with
        VirtualEthernetPair.get_[peer_]interface_name().  The ends of the
        interface are manually configured with the given IPv4 address strings
        (like "10.9.8.2/24").  You may skip the IP configuration by passing None
        as the address for either interface.
        """
        super(VirtualEthernetPair, self).__init__()
        self._is_healthy = True
        self._logger = logging.getLogger("virtual_test_interface")
        self._interface_name = interface_name
        self._peer_interface_name = peer_interface_name
        self._interface_ip = interface_ip
        self._peer_interface_ip = peer_interface_ip

    def setup(self):
        """
        Installs a virtual ethernet interface and configures one side with an IP
        address.  First does some sanity checking and tries to remove an
        existing interface by the same name, and logs messages on failures.
        """
        self._is_healthy = False
        if self._either_interface_exists():
            self._logger.warning("At least one test interface already existed."
                                 "  Attempting to remove.")
            self._remove_test_interface()
            if self._either_interface_exists():
                self._logger.error("Failed to remove unexpected test "
                                   "interface.  Aborting.")
                return

        self._create_test_interface()
        if not self._interface_exists(self._interface_name):
            self._logger.error("Failed to create master test interface.")
            return

        if not self._interface_exists(self._peer_interface_name):
            self._logger.error("Failed to create peer test interface.")
            return
        # Unless you tell the firewall about the interface, you're not going to
        # get any IP traffic through.  Since this is basically a loopback
        # device, just allow all traffic.
        for name in (self._interface_name, self._peer_interface_name):
            code = utils.system("iptables -A INPUT -i %s -j ACCEPT" %
                                name)
            if code != 0:
                self._logger.error("iptables rule addition failed for interface"
                                   " %s" % name)
        self._is_healthy = True

    def teardown(self):
        """
        Removes the interface installed by VirtualEthernetPair.setup(), with
        some simple sanity checks that print warnings when either the interface
        isn't there or fails to be removed.
        """
        for name in (self._interface_name, self._peer_interface_name):
            utils.system("iptables -D INPUT -i %s -j ACCEPT" % name,
                         ignore_status=True)
        if not self._either_interface_exists():
            self._logger.warning("VirtualEthernetPair.teardown() called, "
                                 "but no interface was found.")
            return

        self._remove_test_interface()
        if self._either_interface_exists():
            self._logger.error("Failed to destroy test interface.")

    @property
    def is_healthy(self):
        return self._is_healthy

    @property
    def interface_name(self):
        return self._interface_name

    @property
    def peer_interface_name(self):
        return self._peer_interface_name

    @property
    def interface_ip(self):
        return VirtualEthernetPair._get_ip(self._interface_name)

    @property
    def peer_interface_ip(self):
        return VirtualEthernetPair._get_ip(self._peer_interface_name)

    @property
    def interface_subnet_mask(self):
        return VirtualEthernetPair._get_subnet_mask(self.interface_name)

    @property
    def peer_interface_subnet_mask(self):
        return VirtualEthernetPair._get_subnet_mask(self.peer_interface_name)

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.teardown()

    def _either_interface_exists(self):
        return (self._interface_exists(self._interface_name) or
                self._interface_exists(self._peer_interface_name))

    def _remove_test_interface(self):
        """
        Remove the virtual ethernet device installed by
        _create_test_interface().
        """
        utils.system("ifconfig %s down" % self._interface_name)
        utils.system("ifconfig %s down" % self._peer_interface_name)
        utils.system("ip link delete %s &> /dev/null " % self._interface_name)

    def _create_test_interface(self):
        """
        Set up a virtual ethernet device and configure the host side with a
        fake IP address.
        """
        utils.system("ip link add name %s "
                     "type veth peer name %s &> /dev/null " %
                     (self._interface_name, self._peer_interface_name))
        utils.system("ip link set %s up" % self._interface_name)
        utils.system("ip link set %s up" % self._peer_interface_name)
        if not self._interface_ip is None:
            utils.system("ifconfig %s %s" % (self._interface_name,
                                             self._interface_ip))
        if not self._peer_interface_ip is None:
            utils.system("ifconfig %s %s" % (self._peer_interface_name,
                                             self._peer_interface_ip))
