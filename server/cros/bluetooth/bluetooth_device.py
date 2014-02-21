# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from autotest_lib.client.cros import constants
from autotest_lib.server import autotest


class BluetoothDevice(object):
    """BluetoothDevice is a thin layer of logic over a remote DUT.

    The Autotest host object representing the remote DUT, passed to this
    class on initialization, can be accessed from its host property.

    """

    XMLRPC_BRINGUP_TIMEOUT_SECONDS = 60

    def __init__(self, device_host):
        """Construct a BluetoothDevice.

        @param device_host: host object representing a remote host.

        """
        self.host = device_host
        # Make sure the client library is on the device so that the proxy code
        # is there when we try to call it.
        client_at = autotest.Autotest(self.host)
        client_at.install()
        # Start up the XML-RPC proxy on the client.
        self._proxy = self.host.xmlrpc_connect(
                constants.BLUETOOTH_DEVICE_XMLRPC_SERVER_COMMAND,
                constants.BLUETOOTH_DEVICE_XMLRPC_SERVER_PORT,
                command_name=
                  constants.BLUETOOTH_DEVICE_XMLRPC_SERVER_CLEANUP_PATTERN,
                ready_test_name=
                  constants.BLUETOOTH_DEVICE_XMLRPC_SERVER_READY_METHOD,
                timeout_seconds=self.XMLRPC_BRINGUP_TIMEOUT_SECONDS)


    def reset_on(self):
        """Reset the adapter and settings and power up the adapter.

        @return True on success, False otherwise.

        """
        return self._proxy.reset_on()


    def reset_off(self):
        """Reset the adapter and settings, leave the adapter powered off.

        @return True on success, False otherwise.

        """
        return self._proxy.reset_off()


    def has_adapter(self):
        """@return True if an adapter is present, False if not."""
        return self._proxy.has_adapter()


    def set_powered(self, powered):
        """Set the adapter power state.

        @param powered: adapter power state to set (True or False).

        @return True on success, False otherwise.

        """
        return self._proxy.set_powered(powered)


    def set_discoverable(self, discoverable):
        """Set the adapter discoverable state.

        @param discoverable: adapter discoverable state to set (True or False).

        @return True on success, False otherwise.

        """
        return self._proxy.set_discoverable(discoverable)


    def set_pairable(self, pairable):
        """Set the adapter pairable state.

        @param pairable: adapter pairable state to set (True or False).

        @return True on success, False otherwise.

        """
        return self._proxy.set_pairable(pairable)


    def get_adapter_properties(self):
        """Read the adapter properties from the Bluetooth Daemon.

        @return the properties as a dictionary on success,
            the value False otherwise.

        """
        return json.loads(self._proxy.get_adapter_properties())


    def read_info(self):
        """Read the adapter information from the Kernel.

        @return the information as a tuple of:
          ( address, bluetooth_version, manufacturer_id,
            supported_settings, current_settings, class_of_device,
            name, short_name )

        """
        return json.loads(self._proxy.read_info())


    def get_devices(self):
        """Read information about remote devices known to the adapter.

        @return the properties of each device as a JSON-encoded array of
            dictionaries on success, the value False otherwise.

        """
        return json.loads(self._proxy.get_devices())


    def start_discovery(self):
        """Start discovery of remote devices.

        Obtain the discovered device information using get_devices(), called
        stop_discovery() when done.

        @return True on success, False otherwise.

        """
        return self._proxy.start_discovery()


    def stop_discovery(self):
        """Stop discovery of remote devices.

        @return True on success, False otherwise.

        """
        return self._proxy.stop_discovery()


    def register_profile(self, path, uuid, options):
        """Register new profile (service).

        @param path: Path to the profile object.
        @param uuid: Service Class ID of the service as string.
        @param options: Dictionary of options for the new service, compliant
                        with BlueZ D-Bus Profile API standard.

        @return True on success, False otherwise.

        """
        return self._proxy.register_profile(path, uuid, options)


    def close(self):
        """Tear down state associated with the client."""
        # Turn off the discoverable flag since it may affect future tests.
        self._proxy.set_discoverable(False)
        # Leave the adapter powered off, but don't do a full reset.
        self._proxy.set_powered(False)
        # This kills the RPC server.
        self.host.close()
