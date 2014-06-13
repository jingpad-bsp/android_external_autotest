# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Get Descriptor Sequence

Reference:
  [1] Universal Serial Bus Communication Class MBIM Compliance Testing: 18
      http://www.usb.org/developers/docs/devclass_docs/MBIM-Compliance-1.0.pdf
"""

from usb import control
from usb import util

import common
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_errors
from autotest_lib.client.cros.cellular.mbim_compliance.sequences import sequence


class GetDescriptorSequence(sequence.Sequence):
    """
    Implement the Get Descriptor Sequence.
    Given the vendor and product id for a USB device, obtains the USB
    descriptors for that device.
    """

    def __init__(self, test_context):
        """
        @param test_context: An object that wraps information about the device
               under test.
        """
        self.test_context = test_context


    def run_internal(self):
        """ Run the Get Descriptor Sequence. """
        if self.test_context is None:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceFrameworkError,
                                      'Test context not found')
        device = self.test_context.device
        if device is None:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceFrameworkError,
                                      'Device %04X:%04X not found' %
                                      (self.test_context.id_vendor,
                                       self.test_context.id_product))

        configuration = device.get_active_configuration()
        # Get the actual wTotalLength by retrieving partial descriptor.
        # desc_index corresponds to the index of a configuration. Note that
        # index is of 0 base while configuration is of 1 base.
        descriptor = control.get_descriptor(
                dev=device,
                desc_size=9,
                desc_type=util.DESC_TYPE_CONFIG,
                desc_index=configuration.bConfigurationValue - 1,
                wIndex=0)
        if descriptor is None:
            mbim_errors.log_and_raise(
                    mbim_errors.MBIMComplianceSequenceError,
                    'Failed to find configuration descriptor '
                    'for active configuration of device '
                    '%04X:%04X' % (device.idVendor, device.idProduct))
        # Verify returned data is the requested size.
        descriptor_length = descriptor[0]
        if descriptor_length != 9:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceSequenceError,
                                      'Returned data size (%d) does not match'
                                      'requested value (9)' % descriptor_length)

        descriptor = control.get_descriptor(
                dev=device,
                desc_size=descriptor[2],
                desc_type=util.DESC_TYPE_CONFIG,
                desc_index=configuration.bConfigurationValue - 1,
                wIndex=0)
