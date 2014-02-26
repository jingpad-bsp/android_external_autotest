# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json

from autotest_lib.client.cros import constants
from autotest_lib.server import autotest, hosts


class BluetoothTester(object):
    """BluetoothTester is a thin layer of logic over a remote tester.

    The Autotest host object representing the remote tester, passed to this
    class on initialization, can be accessed from its host property.

    """


    XMLRPC_BRINGUP_TIMEOUT_SECONDS = 60

    def __init__(self, tester_host):
        """Construct a BluetoothTester.

        @param tester_host: host object representing a remote host.

        """
        self.host = tester_host
        # Make sure the client library is on the device so that the proxy code
        # is there when we try to call it.
        client_at = autotest.Autotest(self.host)
        client_at.install()
        # Start up the XML-RPC proxy on the tester.
        self._proxy = self.host.xmlrpc_connect(
                constants.BLUETOOTH_TESTER_XMLRPC_SERVER_COMMAND,
                constants.BLUETOOTH_TESTER_XMLRPC_SERVER_PORT,
                command_name=
                  constants.BLUETOOTH_TESTER_XMLRPC_SERVER_CLEANUP_PATTERN,
                ready_test_name=
                  constants.BLUETOOTH_TESTER_XMLRPC_SERVER_READY_METHOD,
                timeout_seconds=self.XMLRPC_BRINGUP_TIMEOUT_SECONDS)


    def setup(self, profile):
        """Set up the tester with the given profile.

        @param profile: Profile to use for this test, valid values are:
                computer - a standard computer profile

        @return True on success, False otherwise.

        """
        return self._proxy.setup(profile)


    def set_discoverable(self, discoverable, timeout=0):
        """Set the discoverable state of the controller.

        @param discoverable: Whether controller should be discoverable.
        @param timeout: Timeout in seconds before disabling discovery again,
                ignored when discoverable is False, must not be zero when
                discoverable is True.

        @return True on success, False otherwise.

        """
        return self._proxy.set_discoverable(discoverable, timeout)


    def read_info(self):
        """Read the adapter information from the Kernel.

        @return the information as a JSON-encoded tuple of:
          ( address, bluetooth_version, manufacturer_id,
            supported_settings, current_settings, class_of_device,
            name, short_name )

        """
        return json.loads(self._proxy.read_info())


    def discover_devices(self, br_edr=True, le_public=True, le_random=True):
        """Discover remote devices.

        Activates device discovery and collects the set of devices found,
        returning them as a list.

        @param br_edr: Whether to detect BR/EDR devices.
        @param le_public: Whether to detect LE Public Address devices.
        @param le_random: Whether to detect LE Random Address devices.

        @return List of devices found as tuples with the format
                (address, address_type, rssi, flags, base64-encoded eirdata),
                or False if discovery could not be started.

        """
        devices = self._proxy.discover_devices(br_edr, le_public, le_random)
        if devices == False:
            return False

        return (
                (address, address_type, rssi, flags,
                 base64.decodestring(eirdata))
                for address, address_type, rssi, flags, eirdata
                in json.loads(devices)
        )


    def close(self):
        """Tear down state associated with the client."""
        # This kills the RPC server.
        self.host.close()


    def connect(self, address):
        """Connect to device with the given address

        @param address: Bluetooth address.

        """
        self._proxy.connect(address)


    def service_search_request(self, uuids, max_rec_cnt, preferred_size=32):
        """Send a Service Search Request

        @param uuids: List of UUIDs (in 32-bit format) to look for.
        @param max_rec_cnt: Maximum count of returned service records.
        @param preferred_size: Preffered size of UUIDs in bits (16, 32, or 128).

        @return list of found services' service record handles

        """
        return self._proxy.service_search_request(uuids, max_rec_cnt,
                                                  preferred_size)


def create_host_from(device_host):
    """Creates a host object for the Tester associated with a DUT.

    Will raise an exception if there isn't a tester for the DUT.

    @param device_host: Autotest host object for the DUT.

    @return Autotest host object for the Tester.

    """

    device_hostname = device_host.hostname

    parts = device_hostname.split('.')
    parts[0] = parts[0] + '-router'
    tester_hostname = '.'.join(parts)

    return hosts.create_host(tester_hostname)
