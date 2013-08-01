# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.bluetooth import bluetooth_socket
from autotest_lib.server.cros.bluetooth import bluetooth_test


class bluetooth_Sanity_DefaultState(bluetooth_test.BluetoothTest):
    """
    Verify that the Bluetooth adapter has correct state.
    """
    version = 1

    def _log_settings(self, msg, settings):
        strs = []
        if settings & bluetooth_socket.MGMT_SETTING_POWERED:
            strs.append("POWERED")
        if settings & bluetooth_socket.MGMT_SETTING_CONNECTABLE:
            strs.append("CONNECTABLE")
        if settings & bluetooth_socket.MGMT_SETTING_FAST_CONNECTABLE:
            strs.append("FAST-CONNECTABLE")
        if settings & bluetooth_socket.MGMT_SETTING_DISCOVERABLE:
            strs.append("DISCOVERABLE")
        if settings & bluetooth_socket.MGMT_SETTING_PAIRABLE:
            strs.append("PAIRABLE")
        if settings & bluetooth_socket.MGMT_SETTING_LINK_SECURITY:
            strs.append("LINK-SECURITY")
        if settings & bluetooth_socket.MGMT_SETTING_SSP:
            strs.append("SSP")
        if settings & bluetooth_socket.MGMT_SETTING_BREDR:
            strs.append("BR/EDR")
        if settings & bluetooth_socket.MGMT_SETTING_HS:
            strs.append("HS")
        if settings & bluetooth_socket.MGMT_SETTING_LE:
            strs.append("LE")
        logging.debug('msg: %s', " ".join(strs))


    def run_once(self):
        # Reset the adapter to the powered off state.
        if not self.client.reset_off():
            raise error.TestFail('DUT could not be reset to initial state')

        # Read the initial state of the adapter. Verify that it is powered down.
        ( address, bluetooth_version, manufacturer_id,
                    supported_settings, current_settings, class_of_device,
                    name, short_name ) = self.client.read_info()
        self._log_settings('Initial state', current_settings)

        if current_settings & bluetooth_socket.MGMT_SETTING_POWERED:
            raise error.TestFail('Bluetooth adapter is powered')

        # The other kernel settings (connectable, pairable, etc.) reflect the
        # initial state before the bluetooth daemon adjusts them - we're ok
        # with them being on or off during that brief period.
        #
        # Except for discoverable - that one should be off.
        if current_settings & bluetooth_socket.MGMT_SETTING_DISCOVERABLE:
            raise error.TestFail('Bluetooth adapter would be discoverable '
                                 'during power on')

        # Verify that the Bluetooth Daemon sees that it is also powered down,
        # non-discoverable and not discovering devices.
        bluez_properties = self.client.get_adapter_properties()

        if bluez_properties['Powered']:
            raise error.TestFail('Bluetooth daemon Powered property does not '
                                 'match kernel while powered off')
        if bluez_properties['Discoverable']:
            raise error.TestFail('Bluetooth daemon Discoverable property '
                                 'does not match kernel while powered off')
        if bluez_properties['Discovering']:
            raise error.TestFail('Bluetooth daemon believes adapter is '
                                 'discovering while powered off')

        # Power on the adapter, then read the state again. Verify that it is
        # powered up, connectable and pairable (accepting incoming connections)
        # but not discoverable.
        self.client.set_powered(True)
        ( address, bluetooth_version, manufacturer_id,
                    supported_settings, current_settings, class_of_device,
                    name, short_name ) = self.client.read_info()
        self._log_settings("Powered up", current_settings)

        if not current_settings & bluetooth_socket.MGMT_SETTING_POWERED:
            raise error.TestFail('Bluetooth adapter is not powered')
        if not current_settings & bluetooth_socket.MGMT_SETTING_CONNECTABLE:
            raise error.TestFail('Bluetooth adapter is not connectable')
        if not current_settings & bluetooth_socket.MGMT_SETTING_PAIRABLE:
            raise error.TestFail('Bluetooth adapter is not pairable')

        if current_settings & bluetooth_socket.MGMT_SETTING_DISCOVERABLE:
            raise error.TestFail('Bluetooth adapter is discoverable')

        # Verify that the Bluetooth Daemon sees the same state as the kernel
        # and that it's not discovering.
        bluez_properties = self.client.get_adapter_properties()

        if not bluez_properties['Powered']:
            raise error.TestFail('Bluetooth daemon Powered property does not '
                                 'match kernel while powered on')
        if not bluez_properties['Pairable']:
            raise error.TestFail('Bluetooth daemon Pairable property does not '
                                 'match kernel while powered on')

        if bluez_properties['Discoverable']:
            raise error.TestFail('Bluetooth daemon Discoverable property '
                                 'does not match kernel while powered on')
        if bluez_properties['Discovering']:
            raise error.TestFail('Bluetooth daemon believes adapter is '
                                 'discovering while powered on')

        # Finally power off the adapter again, and verify that the adapter has
        # returned to powered down.
        self.client.set_powered(False)
        ( address, bluetooth_version, manufacturer_id,
                    supported_settings, current_settings, class_of_device,
                    name, short_name ) = self.client.read_info()
        self._log_settings("After power down", current_settings)

        if current_settings & bluetooth_socket.MGMT_SETTING_POWERED:
            raise error.TestFail('Bluetooth adapter is powered after power off')

        if current_settings & bluetooth_socket.MGMT_SETTING_DISCOVERABLE:
            raise error.TestFail('Bluetooth adapter would be discoverable '
                                 'during next power on')

        # Verify that the Bluetooth Daemon sees the same state as the kernel.
        bluez_properties = self.client.get_adapter_properties()

        if bluez_properties['Powered']:
            raise error.TestFail('Bluetooth daemon Powered property does not '
                                 'match kernel after power off')
        if bluez_properties['Discoverable']:
            raise error.TestFail('Bluetooth daemon Discoverable property '
                                 'does not match kernel after off')
        if bluez_properties['Discovering']:
            raise error.TestFail('Bluetooth daemon believes adapter is '
                                 'discovering after power off')
