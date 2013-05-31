# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import shill_temporary_profile
from autotest_lib.client.cros import virtual_ethernet_pair
from autotest_lib.client.cros import vpn_server

# This hacks the path so that we can import shill_proxy.
# pylint: disable=W0611
from autotest_lib.client.cros import flimflam_test_path
# pylint: enable=W0611
import shill_proxy

class network_VPNConnect(test.test):
    """The VPN authentication class.

    Starts up a VPN server within a chroot on the other end of a virtual
    ethernet pair and attempts a VPN association using shill.

    """
    # TODO(pstew): We are intentionally choosing a client interface name that
    # shill will ignore so we don't have to either configure Static IP in
    # shill or perform DHCP on this interface.  It means that the
    # configuration process (specifically pinning the VPN connection to
    # the underlying connection) doesn't go wonderfully, but that's not what
    # we are testing here.
    CLIENT_INTERFACE_NAME = 'clientethernet0'
    SERVER_INTERFACE_NAME = 'serverethernet0'
    TEST_PROFILE_NAME = 'testVPN'
    CONNECT_TIMEOUT_SECONDS = 15
    version = 1
    SERVER_ADDRESS = '10.9.8.1'
    CLIENT_ADDRESS = '10.9.8.2'
    NETWORK_PREFIX = 24

    def get_device(self, interface_name):
        """Finds the corresponding Device object for an ethernet
        interface with the name |interface_name|.

        @param interface_name string The name of the interface to check.

        @return DBus interface object representing the associated device.

        """
        device = self._shill_proxy.find_object('Device',
                                               {'Name': interface_name})
        if device is None:
            raise error.TestFail('Device was not found.')

        return device


    def find_ethernet_service(self, interface_name):
        """Finds the corresponding service object for an ethernet
        interface.

        @param interface_name string The name of the associated interface

        @return Service object representing the associated service.

        """
        device = self.get_device(interface_name)
        device_path = shill_proxy.dbus2primitive(device.object_path)
        return self._shill_proxy.find_object('Service', {'Device': device_path})


    def configure_static_ip(self, interface_name, address, prefix_len):
        """Configures the Static IP parameters for the Ethernet interface
        |interface_name| and applies those parameters to the interface by
        forcing a re-connect.

        @param interface_name string The name of the associated interface.
        @param address string the IP address this interface should have.
        @param prefix_len string the IP address prefix for the interface.

        """
        service = self.find_ethernet_service(interface_name)
        service.SetProperty("StaticIP.Address", address)
        service.SetProperty("StaticIP.Prefixlen", prefix_len)
        service.Disconnect()
        service.Connect()


    def get_vpn_server(self):
        """Returns a VPN server instance."""
        if self._vpn_type == 'l2tpipsec-psk':
            return vpn_server.L2TPIPSecVPNServer('psk',
                                                 self.SERVER_INTERFACE_NAME,
                                                 self.SERVER_ADDRESS,
                                                 self.NETWORK_PREFIX)
        elif self._vpn_type == 'l2tpipsec-cert':
            return vpn_server.L2TPIPSecVPNServer('cert',
                                                 self.SERVER_INTERFACE_NAME,
                                                 self.SERVER_ADDRESS,
                                                 self.NETWORK_PREFIX)
        else:
            raise error.TestFail('Unknown vpn server type %s' % self._vpn_type)


    def get_vpn_client_properties(self):
        """Returns VPN configuration properties."""
        if self._vpn_type == 'l2tpipsec-psk':
            return {
                'L2TPIPsec.Password': vpn_server.L2TPIPSecVPNServer.CHAP_SECRET,
                'L2TPIPsec.PSK': vpn_server.L2TPIPSecVPNServer.IPSEC_PASSWORD,
                'L2TPIPsec.User':vpn_server.L2TPIPSecVPNServer.CHAP_USER,
                'Name': 'test-vpn-psk',
                'Provider.Host': self.SERVER_ADDRESS,
                'Provider.Type': 'l2tpipsec',
                'Type': 'vpn',
                'VPN.Domain': 'test-vpn-psk-domain'
            }
        else:
            raise error.TestFail('Unknown vpn client type %s' % self._vpn_type)


    def connect_vpn(self):
        """Connects the client to the VPN server."""
        proxy = self._shill_proxy
        service = proxy.get_service(self.get_vpn_client_properties())
        service.Connect()
        result = proxy.wait_for_property_in(service,
                                            proxy.SERVICE_PROPERTY_STATE,
                                            ('ready', 'online'),
                                            self.CONNECT_TIMEOUT_SECONDS)
        (successful, _, _) = result
        if not successful:
            raise error.TestFail('VPN connection failed')


    def run_once(self, vpn_type=None):
        """Test main loop."""
        self._shill_proxy = shill_proxy.ShillProxy()
        manager = self._shill_proxy.manager
        server_address_and_prefix = '%s/%d' % (self.SERVER_ADDRESS,
                                               self.NETWORK_PREFIX)
        client_address_and_prefix = '%s/%d' % (self.CLIENT_ADDRESS,
                                               self.NETWORK_PREFIX)
        self._vpn_type = vpn_type

        with shill_temporary_profile.ShillTemporaryProfile(
                manager, profile_name=self.TEST_PROFILE_NAME):
            with virtual_ethernet_pair.VirtualEthernetPair(
                    interface_name=self.SERVER_INTERFACE_NAME,
                    peer_interface_name=self.CLIENT_INTERFACE_NAME,
                    peer_interface_ip=client_address_and_prefix,
                    interface_ip=server_address_and_prefix) as ethernet_pair:
                if not ethernet_pair.is_healthy:
                    raise error.TestFail('Virtual ethernet pair failed.')

                with self.get_vpn_server() as server:
                    self.connect_vpn()
