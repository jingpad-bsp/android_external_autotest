# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import site_eap_certs
from autotest_lib.client.cros import flimflam_test_path
from autotest_lib.client.cros import hostapd_server
from autotest_lib.client.cros import shill_temporary_profile
from autotest_lib.client.cros import virtual_ethernet_pair

import shill_proxy

class network_8021xWiredAuthentication(test.test):
    """The 802.1x EAP wired authentication class.

    Runs hostapd on one side of an ethernet pair, and shill on the other.
    Configures the Ethernet service with 802.1x credentials and ensures
    that when shill detects an EAP authenticator, it is successful in
    using its credentials to gain access.

    """
    INTERFACE_NAME = 'pseudoethernet0'
    AUTHENTICATION_FLAG = 'EapAuthenticationCompleted'
    TEST_PROFILE_NAME = 'test1x'
    version = 1

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


    def get_authenticated_flag(self, interface_name):
        """Checks whether |interface_name| has successfully negotiated
        802.1x.

        @param interface_name string The name of the interface to check.

        @return True if the authenticated flag is set, False otherwise.

        """
        device = self.get_device(interface_name)
        device_properties = device.GetProperties(utf8_strings=True)
        logging.info('Device properties are %r', device_properties)
        return shill_proxy.dbus2primitive(
                device_properties[self.AUTHENTICATION_FLAG])


    def find_ethernet_service(self, interface_name):
        """Finds the corresponding service object for an ethernet
        interface.

        @param interface_name string The name of the associated interface

        @return Service object representing the associated service.

        """
        device = self.get_device(interface_name)
        device_path = shill_proxy.dbus2primitive(device.object_path)
        return self._shill_proxy.find_object('Service', {'Device': device_path})


    def configure_credentials(self, interface_name):
        """Adds authentication properties to the Ethernet service.

        @param interface_name string The name of the associated interface

        """
        service = self.find_ethernet_service(interface_name)
        service.SetProperty('EAP.EAP', hostapd_server.HostapdServer.EAP_TYPE)
        service.SetProperty('EAP.InnerEAP',
                            'auth=%s' % hostapd_server.HostapdServer.EAP_PHASE2)
        service.SetProperty('EAP.Identity',
                            hostapd_server.HostapdServer.EAP_USERNAME)
        service.SetProperty('EAP.Password',
                            hostapd_server.HostapdServer.EAP_PASSWORD)
        service.SetProperty('EAP.CACertPEM', site_eap_certs.ca_cert_1)


    def run_once(self):
        """Test main loop."""
        self._shill_proxy = shill_proxy.ShillProxy()

        with shill_temporary_profile.ShillTemporaryProfile(
                self._shill_proxy.manager, profile_name=self.TEST_PROFILE_NAME):
            with virtual_ethernet_pair.VirtualEthernetPair(
                    peer_interface_name=self.INTERFACE_NAME,
                    peer_interface_ip=None) as ethernet_pair:
                if not ethernet_pair.is_healthy:
                    raise error.TestFail('Virtual ethernet pair failed.')

                if self.get_authenticated_flag(self.INTERFACE_NAME):
                    raise error.TestFail('Authentication flag already set.')

                with hostapd_server.HostapdServer(
                        interface=ethernet_pair.interface_name) as hostapd:
                    # Wait for hostapd to initialize.
                    time.sleep(1)
                    if not hostapd.running():
                        raise error.TestFail('hostapd process exited.')

                    self.configure_credentials(self.INTERFACE_NAME)
                    hostapd.send_eap_packets()
                    time.sleep(10)
                    if not self.get_authenticated_flag(self.INTERFACE_NAME):
                        raise error.TestFail('Authentication did not complete.')
