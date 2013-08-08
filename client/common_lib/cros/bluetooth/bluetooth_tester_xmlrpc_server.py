#!/usr/bin/env python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import logging
import logging.handlers

import common
from autotest_lib.client.common_lib.cros import xmlrpc_server
from autotest_lib.client.common_lib.cros.bluetooth import bluetooth_socket
from autotest_lib.client.cros import constants


class BluetoothTesterXmlRpcDelegate(xmlrpc_server.XmlRpcDelegate):
    """Exposes Tester methods called removely during Bluetooth autotests.

    All instance methods of this object without a preceding '_' are exposed via
    an XML-RPC server. This is not a stateless handler object, which means that
    if you store state inside the delegate, that state will remain aroun dfor
    future calls.
    """

    BR_EDR_LE_PROFILE = (
            bluetooth_socket.MGMT_SETTING_POWERED |
            bluetooth_socket.MGMT_SETTING_CONNECTABLE |
            bluetooth_socket.MGMT_SETTING_PAIRABLE |
            bluetooth_socket.MGMT_SETTING_SSP |
            bluetooth_socket.MGMT_SETTING_BREDR |
            bluetooth_socket.MGMT_SETTING_LE)

    PROFILE_SETTINGS = {
        'computer': BR_EDR_LE_PROFILE,
    }

    PROFILE_CLASS = {
        'computer': 0x000104,
    }

    PROFILE_NAMES = {
        'computer': ('ChromeOS Bluetooth Tester', 'Tester'),
    }


    def __init__(self):
        super(BluetoothTesterXmlRpcDelegate, self).__init__()

        # Open the Bluetooth Control socket to the kernel which provides us
        # the needed raw management access to the Bluetooth Host Subsystem.
        self._control = bluetooth_socket.BluetoothControlSocket()
        # This is almost a constant, but it might not be forever.
        self.index = 0


    def setup(self, profile):
        """Set up the tester with the given profile.

        @param profile: Profile to use for this test, valid values are:
                computer - a standard computer profile

        @return True on success, False otherwise.

        """
        if not (self._setup_profile_settings(profile) and
                self._setup_profile_class(profile) and
                self._setup_profile_names(profile)):
            return False

        logging.info('Tester setup with profile: %s', profile)
        return True


    def _setup_profile_settings(self, profile):
        """Set up the controller with settings from the given profile.

        @param profile: profile to use, see setup().

        @return True on success, False otherwise.

        """
        profile_settings = self.PROFILE_SETTINGS[profile]
        # Make sure all of the settings are supported by the controller.
        ( address, bluetooth_version, manufacturer_id,
          supported_settings, current_settings, class_of_device,
          name, short_name ) = self._control.read_info(self.index)
        if profile_settings & supported_settings != profile_settings:
            logging.warning('Controller does not support requested settings')
            return False

        # Send the individual commands to set up the adapter. There is no
        # command to set the BR/EDR flag, that's something that's either on
        # or off in the chip. We do, of course, want to check for it later.
        if not self._control.set_powered(
                self.index,
                profile_settings & bluetooth_socket.MGMT_SETTING_POWERED):
            logging.warning('Failed to set powered setting')
            return False
        if (self._control.set_connectable(
                self.index,
                profile_settings & bluetooth_socket.MGMT_SETTING_CONNECTABLE)
                    is None):
            logging.warning('Failed to set connectable setting')
            return False
        if (self._control.set_fast_connectable(
                self.index,
                profile_settings &
                bluetooth_socket.MGMT_SETTING_FAST_CONNECTABLE)
                    is None):
            logging.warning('Failed to set fast connectable setting')
            return False
        if (self._control.set_pairable(
                self.index,
                profile_settings & bluetooth_socket.MGMT_SETTING_PAIRABLE)
                    is None):
            logging.warning('Failed to set pairable setting')
            return False
        if (self._control.set_link_security(
                self.index,
                profile_settings & bluetooth_socket.MGMT_SETTING_LINK_SECURITY)
                    is None):
            logging.warning('Failed to set link security setting')
            return False
        if (self._control.set_ssp(
                self.index,
                profile_settings & bluetooth_socket.MGMT_SETTING_SSP)
                    is None):
            logging.warning('Failed to set SSP setting')
            return False
        if (self._control.set_hs(
                self.index,
                profile_settings & bluetooth_socket.MGMT_SETTING_HS)
                    is None):
            logging.warning('Failed to set High Speed setting')
            return False
        if (self._control.set_le(
                self.index,
                profile_settings & bluetooth_socket.MGMT_SETTING_LE)
                    is None):
            logging.warning('Failed to set Low Energy setting')
            return False

        # Fetch the settings again and make sure they're all set correctly,
        # including the BR/EDR flag.
        ( address, bluetooth_version, manufacturer_id,
          supported_settings, current_settings, class_of_device,
          name, short_name ) = self._control.read_info(self.index)
        if profile_settings != current_settings:
            logging.warning('Controller settings did not match those set: '
                            '%x != %x', current_settings, profile_settings)
            return False

        return True


    def _setup_profile_class(self, profile):
        """Set up the controller with device class from the given profile.

        @param profile: profile to use, see setup().

        @return True on success, False otherwise.

        """
        profile_class = self.PROFILE_CLASS[profile]
        # Split our the major and minor class; it's listed as a kernel bug that
        # we supply these to the kernel without shifting the bits over to take
        # out the CoD format field, so this might have to change one day.
        major_class = (profile_class & 0x00ff00) >> 8
        minor_class = profile_class & 0x0000ff
        class_of_device = self._control.set_device_class(
                self.index, major_class, minor_class)
        if class_of_device is None:
            logging.warning('Failed to set device class')
            return False

        # Verify that the device class was set correctly, including the Service
        # Class fields; warn about those separately since the fix is probably
        # "reboot the tester".
        if class_of_device != profile_class:
            if class_of_device & 0x00ffff == profile_class & 0x00ffff:
                logging.warning('Class of device matched that set, but '
                                'Service Class field did not: %x != %x '
                                'Reboot Tester? ',
                                class_of_device, profile_class)
            else:
                logging.warning('Class of device did not match that set: '
                                '%x != %x', class_of_device, profile_class)
            return False

        return True


    def _setup_profile_names(self, profile):
        """Set up the controller with names from the given profile.

        @param profile: profile to use, see setup().

        @return True on success, False otherwise.

        """
        (name, short_name) = self.PROFILE_NAMES[profile]
        names = self._control.set_local_name(self.index, name, short_name)
        if names is None:
            logging.warning('Failed to set local name')
            return False

        # Verify they matched what we set, and were not mangled or truncated.
        (set_name, set_short_name) = names
        if set_name != name:
            logging.warning('Local name did not match that set: "%s" != "%s"',
                            set_name, name)
            return False
        elif set_short_name != short_name:
            logging.warning('Short name did not match that set: "%s" != "%s"',
                            set_short_name, short_name)
            return False

        return True


    def discover_devices(self, br_edr=True, le_public=True, le_random=True):
        """Discover remote devices.

        Activates device discovery and collects the set of devices found,
        returning them as a list.

        @param br_edr: Whether to detect BR/EDR devices.
        @param le_public: Whether to detect LE Public Address devices.
        @param le_random: Whether to detect LE Random Address devices.

        @return List of devices found as JSON-encoded tuples with the format
                (address, address_type, rssi, flags, base64-encoded eirdata),
                or False if discovery could not be started.

        """
        address_type = 0
        if br_edr:
            address_type |= 0x1
        if le_public:
            address_type |= 0x2
        if le_random:
            address_type |= 0x4

        set_type = self._control.start_discovery(self.index, address_type)
        if set_type != address_type:
            logging.warning('Discovery address type did not match that set: '
                            '%x != %x', set_type, address_type)
            return False

        devices = self._control.get_discovered_devices(self.index)
        return json.dumps([
                (address, address_type, rssi, flags,
                 base64.encodestring(eirdata))
                for address, address_type, rssi, flags, eirdata in devices
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = '/dev/log')
    logging.getLogger().addHandler(handler)
    logging.debug('bluetooth_tester_xmlrpc_server main...')
    server = xmlrpc_server.XmlRpcServer(
            'localhost',
            constants.BLUETOOTH_TESTER_XMLRPC_SERVER_PORT)
    server.register_delegate(BluetoothTesterXmlRpcDelegate())
    server.run()
