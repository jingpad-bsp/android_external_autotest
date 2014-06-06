# Copyright (c) 2014 The chromimn OS Authros. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from usb import core


class TestContext:
    """
    Context of device under test.
    """

    _id_vendor = 0x12d1
    _id_product = 0x15bb
    _device = None

    def __init__(self):
        self._device = core.find(idVendor=self._id_vendor,
                                 idProduct=self._id_product)


    @property
    def id_vendor(self):
        """
        Refers to idVendor.

        @returns idVendor for the device

        """
        return self._id_vendor


    @property
    def id_product(self):
        """
        Refers to idProduct.

        @returns idProduct for the device

        """
        return self._id_product


    @property
    def device(self):
        """
        Refers to usb.core.Descriptor object under test

        @returns device object under test

        """
        return self._device
