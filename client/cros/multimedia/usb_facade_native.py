# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""An interface to access the local USB facade."""

import glob
import logging

from autotest_lib.client.common_lib import base_utils


class USBDeviceDriversManagerError(Exception):
    """Error in USBDeviceDriversManager."""
    pass


class USBDeviceDriversManager(object):
    """The class to control the USB drivers associated with a USB device.

    Properties:
        _device_product_name: The product name given to the USB device.
        _device_bus_id: The bus ID of the USB device in the host.

    """
    # The file to write to bind USB drivers of specified device
    _USB_BIND_FILE_PATH = '/sys/bus/usb/drivers/usb/bind'
    # The file to write to unbind USB drivers of specified device
    _USB_UNBIND_FILE_PATH = '/sys/bus/usb/drivers/usb/unbind'

    def __init__(self):
        """Initializes the manager.

        _device_product_name and _device_bus_id are initially set to None.
        """
        self._device_product_name = None
        self._device_bus_id = None


    def _find_usb_device_bus_id(self, product_name):
        """Finds the bus ID of the USB device with the given product name.

        @param product_name: The product name of the USB device as it appears
                             to the host. But it is case-insensitive in this
                             method.

        @returns: The bus ID of the USB device if it is detected by the host
                  successfully; or None if there is no such device with the
                  given product name.

        """
        devices_glob_search_path = '/sys/bus/usb/drivers/usb/usb?/'
        product_name_lowercase = product_name.lower()
        for path in glob.glob(devices_glob_search_path + '*/product'):
            current_product_name = base_utils.read_one_line(path).lower()
            if product_name_lowercase in current_product_name:
                bus_id = path[len(devices_glob_search_path):]
                bus_id = bus_id[:-len('/product')]
                return bus_id
        logging.error('Bus ID of %s not found', product_name)
        return None


    def set_usb_device(self, product_name):
        """Sets _device_product_name and _device_bus_id if it can be found.

        @param product_name: The product name of the USB device as it appears
                             to the host.

        @raises: USBDeviceDriversManagerError if device bus ID cannot be found
                 for the device with the given product name.

        """
        device_bus_id = self._find_usb_device_bus_id(product_name)
        if device_bus_id is None:
            error_message = 'Cannot find device with product name: %s'
            raise USBDeviceDriversManagerError(error_message % product_name)
        else:
            self._device_product_name = product_name
            self._device_bus_id = device_bus_id
