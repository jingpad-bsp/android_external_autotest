# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides the utilities for bluetooth audio using chameleon."""

import logging

from autotest_lib.client.bin import utils


_PIN = '0000'
_SEARCH_TIMEOUT = 30.0
_PAIRING_TIMEOUT = 5.0


class ChameleonBluetoothAudioError(Exception):
    """Error in this module."""
    pass


def connect_bluetooth_module(bt_adapter, target_mac_address,
                             timeout=_SEARCH_TIMEOUT):
    """Controls Cros device to connect to bluetooth module on audio board.

    @param bt_adapter: A BluetoothDevice object to control bluetooth adapter
                       on Cros device.
    @param target_mac_address: The MAC address of bluetooth module to be
                               connected.
    @param timeout: Timeout in seconds to search for bluetooth module.

    @raises: ChameleonBluetoothAudioError if Cros device fails to connect to
             bluetooth module on audio board.

    """
    # Resets bluetooth adapter on Cros device.
    bt_adapter.reset_on()

    # Starts discovery mode of bluetooth adapter.
    bt_adapter.start_discovery()

    def _find_device():
        """Controls bluetooth adapter to search for bluetooth module.

        @returns: True if there is a bluetooth device with MAC address
                  matches target_mac_address. False otherwise.

        """
        devices = bt_adapter.get_devices()
        for device in devices:
            if device['Address'] == target_mac_address:
                logging.info('Found bluetooth device %r', device)
                return True
        return False

    # Searches for bluetooth module with given MAC address.
    found_device = utils.wait_for_value(_find_device, True, timeout_sec=timeout)

    if not found_device:
        raise ChameleonBluetoothAudioError(
                'Can not find bluetooth module with MAC address %s' %
                target_mac_address)

    # Pairs the bluetooth adapter with bluetooth module.
    if not bt_adapter.pair_legacy_device(
            target_mac_address, _PIN, _PAIRING_TIMEOUT):
        raise ChameleonBluetoothAudioError(
                'Failed to pair Cros device and bluetooth module %s' %
                target_mac_address)

    # Disconnects from bluetooth module to clean up the state.
    if not bt_adapter.disconnect_device(target_mac_address):
        raise ChameleonBluetoothAudioError(
                'Failed to let Cros device disconnect from bluetooth module %s' %
                target_mac_address)

    # Connects to bluetooth module.
    if not bt_adapter.connect_device(target_mac_address):
        raise ChameleonBluetoothAudioError(
                'Failed to let Cros device connect to bluetooth module %s' %
                target_mac_address)

    logging.info('Bluetooth module at %s is connected', target_mac_address)
