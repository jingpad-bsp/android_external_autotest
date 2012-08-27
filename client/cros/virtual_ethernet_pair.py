# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
VirtualEthernetPair provides methods for setting up and tearing down a virtual
ethernet interface for use in tests.  You will probably need to be root on test
devices to use this class.  The constructor allows you to specify your IP's to
assign to both ends of the pair, however, if you wish to leave the interface
unconfigured, simply pass None.

Example usage:
vif = virtual_ethernet_pair.VirtualEthernetPair(interface_prefix="veth_",
                                                interface_ip="192.168.177.1",
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

from autotest_lib.client.bin import utils

class VirtualEthernetPair:
    @staticmethod
    def _get_interface_ip(interface_name):
        """
        Returns the IPv4 address for |interface_name| if configured, and returns
        None if that address could not be found.
        """
        cmd_get_ip = ("ip addr show %s 2> /dev/null | grep 'inet ' | "
                      "sed -E 's/.*inet ([0-9]+.[0-9]+.[0-9]+.[0-9]+).*/\\1/'" %
                      interface_name)
        addr = utils.system_output(cmd_get_ip)
        if addr == "":
            return None
        return addr

    @staticmethod
    def _interface_exists(interface_name):
        """
        Returns True iff we found an interface with name |interface_name|.
        """
        return utils.system("ifconfig | grep %s &> /dev/null" % interface_name,
                            ignore_status=True) == 0

    def __init__(self,
                 interface_prefix="veth_",
                 interface_ip="10.9.8.1",
                 peer_interface_ip="10.9.8.2"):
        """
        Construct a object managing a virtual ethernet pair.  One end of the
        interface will be called |interface_prefix|_master, and the peer end
        |interface_prefix|_slave.  You may get the resulting names with your
        prefix with VirtualEthernetPair.get_[peer_]interface_name().  The ends
        of the interface are manually configured with the given IPv4 address
        strings (like "10.9.8.2").  You may skip the IP configuration by passing
        None as the address for either interface.
        """
        self._is_healthy = True
        self._logger = logging.getLogger("virtual_test_interface")
        self._interface_name = interface_prefix + "master"
        self._peer_interface_name = interface_prefix + "slave"
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

        self._is_healthy = True

    def teardown(self):
        """
        Removes the interface installed by VirtualEthernetPair.setup(), with
        some simple sanity checks that print warnings when either the interface
        isn't there or fails to be removed.
        """
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
        return VirtualEthernetPair._get_interface_ip(self._interface_name)

    @property
    def peer_interface_ip(self):
        return VirtualEthernetPair._get_interface_ip(self._peer_interface_name)

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
            utils.system("ifconfig %s %s/24" % (self._interface_name,
                                             self._interface_ip))
        if not self._peer_interface_ip is None:
            utils.system("ifconfig %s %s/24" % (self._peer_interface_name,
                                                self._peer_interface_ip))
