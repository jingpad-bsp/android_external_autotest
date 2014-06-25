# Copyright (c) 2014 The chromimn OS Authros. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from usb import core


# Device types.
DEVICE_TYPE_UNKNOWN = 0
DEVICE_TYPE_MBIM = 1
DEVICE_TYPE_NCM_MBIM = 2


class TestContext:
    """ Context of device under test. """

    def __init__(self):
        self._id_vendor = 0x1983
        self._id_product = 0x1003
        self._device = core.find(idVendor=self._id_vendor,
                                 idProduct=self._id_product)

        # Once a device has been discovered, and its USB descriptors have been
        # parsed, this property determines whether the discovered device is an
        # MBIM only function (DEVICE_TYPE_MBIM) or an NCM/MBIM combined function
        # (DEVICE_TYPE_NCM_MBIM). The other |*_interface| properties are
        # determined accordingly.
        self.device_type = DEVICE_TYPE_UNKNOWN

        # The USB Descriptor for the communication interface for the modem. This
        # descirptor corresponds to the alternate setting of the interface over
        # which mbim control command can be transferred.
        self.mbim_communication_interface = None

        # The USB Descriptor for the communication interface for the modem. This
        # descriptor corresponds to the alternate setting of the interface over
        # which ncm control command can be transferred.
        self.ncm_communication_interface = None

        # The USB Descriptor for the CDC Data interface for the modem. This
        # descriptor corresponds to the alternate setting of the interface over
        # which no data can be transferred.
        self.no_data_data_interface = None

        # The USB Descriptor for the CDC Data interface for the modem. This
        # descriptor corresponds to the alternate setting of the interface over
        # which MBIM data must be transferred.
        self.mbim_data_interface = None

        # The USB Descriptor for the CDC Data interface for the modem. This
        # descriptor corresponds to the alternate setting of the interface over
        # which NCM data must be transferred.
        self.ncm_data_interface = None


    @property
    def device(self):
        """
        Refer to the device under test.

        @returns The usb.core.Device object.

        """
        return self._device
