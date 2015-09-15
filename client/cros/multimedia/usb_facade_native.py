# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""An interface to access the local USB facade."""

import glob
import logging
import os

from autotest_lib.client.common_lib import base_utils


class USBFacadeNativeError(Exception):
    """Error in USBFacadeNative."""
    pass


class USBFacadeNative(object):
    """Facade to access the USB-related functionality.

    Property:
      _drivers_manager: A USBDeviceDriversManager object used to manage the
                        status of drivers associated with the USB audio gadget
                        on the host side.

    """
    _DEFAULT_DEVICE_PRODUCT_NAME = 'Linux USB Audio Gadget'

    def __init__(self):
        """Initializes the USB facade.

        The _drivers_manager is set with a USBDeviceDriversManager, which is
        used to control the visibility and availability of a USB device on a
        host Cros device.
        """
        self._drivers_manager = USBDeviceDriversManager()


    def plug(self):
        """Sets and plugs the USB device into the host.

        The USB device is initially set to one with the default product name,
        which is assumed to be the name of the USB audio gadget on Chameleon.
        """
        self._drivers_manager.set_usb_device(self._DEFAULT_DEVICE_PRODUCT_NAME)
        self._drivers_manager.bind_usb_drivers()


    def unplug(self):
        """Unplugs the USB device from the host."""
        self._drivers_manager.unbind_usb_drivers()


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
    # The file path that exists when drivers are bound for current device
    _USB_BOUND_DRIVERS_FILE_PATH = '/sys/bus/usb/drivers/usb/%s/driver'

    def __init__(self):
        """Initializes the manager.

        _device_product_name and _device_bus_id are initially set to None.
        """
        self._device_product_name = None
        self._device_bus_id = None


    def _find_usb_device_bus_id(self, product_name):
        """Finds the bus ID of the USB device with the given product name.

        @param product_name: The product name of the USB device as it appears
                             to the host.

        @returns: The bus ID of the USB device if it is detected by the host
                  successfully; or None if there is no such device with the
                  given product name.

        """
        def product_matched(path):
            """Checks if the product field matches expected product name.

            @returns: True if the product name matches, False otherwise.

            """
            return base_utils.read_one_line(path) == product_name

        # Find product field at these possible paths:
        # '/sys/bus/usb/drivers/usb/usbX/X-Y/product' => bus id is X-Y.
        # '/sys/bus/usb/drivers/usb/usbX/X-Y/X-Y.Z/product' => bus id is X-Y.Z.
        glob_search_path = '/sys/bus/usb/drivers/usb/usb?/'

        for search_root_path in glob.glob(glob_search_path):
            for root, dirs, _ in os.walk(search_root_path):
                for bus_id in dirs:
                    product_path = os.path.join(root, bus_id, 'product')
                    if not os.path.exists(product_path):
                        continue
                    if not product_matched(product_path):
                        continue
                    logging.debug(
                            'Bus ID of %s found: %s', product_name, bus_id)
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


    def _drivers_are_bound(self):
        """Checks whether the drivers with the of current device are bound.

        If the drivers are already bound, calling bind_usb_drivers will be
        redundant and also result in an error.

        @return: True if the path to the drivers exist, meaning the drivers
                 are already bound. False otherwise.

        """
        driver_path = self._USB_BOUND_DRIVERS_FILE_PATH % self._device_bus_id
        return os.path.exists(driver_path)


    def bind_usb_drivers(self):
        """Binds the USB driver(s) of the current device to the host.

        This is applied to all the drivers associated with and listed under
        the USB device with the current _device_product_name and _device_bus_id.

        @raises: USBDeviceDriversManagerError if device bus ID for this instance
                 has not been set yet.

        """
        if self._device_bus_id is None:
            raise USBDeviceDriversManagerError('USB Bus ID is not set yet.')
        if self._drivers_are_bound():
            return
        base_utils.open_write_close(self._USB_BIND_FILE_PATH,
                self._device_bus_id)


    def unbind_usb_drivers(self):
        """Unbinds the USB driver(s) of the current device from the host.

        This is applied to all the drivers associated with and listed under
        the USB device with the current _device_product_name and _device_bus_id.

        @raises: USBDeviceDriversManagerError if device bus ID for this instance
                 has not been set yet.

        """
        if self._device_bus_id is None:
            raise USBDeviceDriversManagerError('USB Bus ID is not set yet.')
        if not self._drivers_are_bound():
            return
        base_utils.open_write_close(self._USB_UNBIND_FILE_PATH,
                                    self._device_bus_id)
