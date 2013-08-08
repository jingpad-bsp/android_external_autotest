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


def create_host_from(client_host):
    """Creates a host object for the Tester associated with a DUT.

    Will raise an exception if there isn't a tester for the DUT.

    @param client_host: Autotest host object for the DUT.

    @return Autotest host object for the Tester.

    """

    client_hostname = client_host.hostname

    parts = client_hostname.split('.')
    parts[0] = parts[0] + '-bluetooth'
    tester_hostname = '.'.join(parts)

    return hosts.create_host(tester_hostname)
