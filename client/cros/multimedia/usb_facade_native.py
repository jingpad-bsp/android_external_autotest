# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""An adapter to access the local USB facade."""


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
