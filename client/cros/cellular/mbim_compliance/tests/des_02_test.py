# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
DES_02 Descriptors Validation for MBIM Only Functions

Reference:
  [1] Universal Serial Bus Communication Class MBIM Compliance Testing: 23
      http://www.usb.org/developers/docs/devclass_docs/MBIM-Compliance-1.0.pdf
"""

from usb import util

import common
from autotest_lib.client.cros.cellular.mbim_compliance import containers
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_errors
from autotest_lib.client.cros.cellular.mbim_compliance import utils
from autotest_lib.client.cros.cellular.mbim_compliance.sequences \
  import get_descriptor_sequence
from autotest_lib.client.cros.cellular.mbim_compliance.tests import test

class DES_02_Test(test.Test):
    """ Implement the DES_2 Descriptors Validation for MBIM Only Functions. """

    def __init__(self, test_context):
        self.test_context = test_context


    def run_internal(self):
        """
        Run the DES_02 test.

        @returns a bool value to indicate whether the test is passed.

        """
        # Precondition.
        get_descriptor_sequence.GetDescriptorSequence(self.test_context).run()
        device = self.test_context.device
        if not device:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceTestError,
                                      'Device not found')

        active_configuration = device.get_active_configuration()
        # Get interface association descriptor.
        interface_association_descriptor = (
                utils.get_configuration_extra_descriptors(
                        active_configuration.extra))
        # Test step 1
        # Assertion: [MBIM 1.0] - 6.3#1
        interfaces = util.find_descriptor(active_configuration,
                                          find_all=True,
                                          bAlternateSetting=0,
                                          bNumEndpoints=1,
                                          bInterfaceClass=0x02,
                                          bInterfaceSubClass=0x0E,
                                          bInterfaceProtocol=0x00)
        if interfaces is None:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceTestError,
                                      'Communication interface: not found')
        for interface in interfaces:
            # Test step 2
            # Get header functional descriptor, union functional descriptor,
            # MBIM functional descriptor and MBIM extended functional
            # descriptor.
            extra_descriptors = utils.get_interface_extra_descriptors(
                   interface.extra)

            # Assertion: [MBIM 1.0] - 6.3#2
            found_header_functional_descriptor = False
            found_union_functional_descriptor = False
            found_MBIM_functional_descriptor = False
            for descriptor in extra_descriptors:
                if descriptor.bDescriptorSubtype == 0x00:
                    found_header_functional_descriptor = True
                elif descriptor.bDescriptorSubtype == 0x06:
                    found_union_functional_descriptor = True
                elif descriptor.bDescriptorSubtype == 0x1B:
                    found_MBIM_functional_descriptor = True

            if not(found_header_functional_descriptor and
                   found_union_functional_descriptor and
                   found_MBIM_functional_descriptor):
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceAssertionError,
                        'mbim1.0:6.3#2')

          # Test step 3
            header_functional_descriptor_indices = self.descriptor_filter(
                    containers.HeaderFunctionalDescriptor, extra_descriptors)
            if len(header_functional_descriptor_indices) > 1:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceGenericAssertionError,
                        'Header functional descriptor: more than one found')

            header_descriptor_index = header_functional_descriptor_indices[0]
            header_functional_descriptor = (
                    extra_descriptors[header_descriptor_index])

            if not(header_functional_descriptor.bDescriptorType == 0x24 and
                   header_functional_descriptor.bDescriptorSubtype == 0x00 and
                   header_functional_descriptor.bLength == 5 and
                   header_functional_descriptor.bcdCDC >= 0x0120):
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceGenericAssertionError,
                        'Header functional descriptor: wrong value(s)')

            # Test step 4
            union_functional_descriptor_indices = self.descriptor_filter(
                    containers.UnionFunctionalDescriptor, extra_descriptors)
            union_descriptor_index = union_functional_descriptor_indices[0]
            if len(union_functional_descriptor_indices) > 1:
                for index in union_functional_descriptor_indices[1:]:
                    if (extra_descriptors[index] !=
                        extra_descriptors[union_descriptor_index]):
                        mbim_errors.log_and_raise(
                                mbim_errors.MBIMComplianceGenerisAssertionError,
                                'More than one union functional descriptor'
                                'found')

            # Assertion:[MBIM 1.0] - 6.3#3
            if union_descriptor_index < header_descriptor_index:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceAssertionError,
                        'mbim1.0:6.3#3')

            union_functional_descriptor = (
                    extra_descriptors[union_descriptor_index])

            # Find the bInterfaceNumber with matched fields.
            # Assertion: [MBIM 1.0] - 6.3#4
            # Get interface numbers with alternate setting 0.
            interface_with_alternate_setting_0 = util.find_descriptor(
                    active_configuration,
                    find_all=True,
                    bAlternateSetting=0,
                    bNumEndpoints=0,
                    bInterfaceClass=0x0A,
                    bInterfaceSubClass=0x00,
                    bInterfaceProtocol=0x02)
            # There should be exactly one cdc data interface with alternate
            # setting 0.
            if len(interface_with_alternate_setting_0) != 1:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceGenericAssertionError,
                        'Exactly one CDC data interface with alternate setting '
                        '0 should be found.')
            # Check if there is any endpoint descriptor with alternate
            # setting 0.
            endpoint_descriptors = [
                    endpoint for endpoint in
                            interface_with_alternate_setting_0[0]]
            if endpoint_descriptors:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceGenericAssertionError,
                        'Unexpected Endpoint descriptors in alternate setting '
                        '0.')

            interface_number_with_alternate_setting_0 = (
                    interface_with_alternate_setting_0[0].bInterfaceNumber)

            # Get interface numbers with alternate setting 1.
            interface_with_alternate_setting_1 = util.find_descriptor(
                    active_configuration,
                    find_all=True,
                    bAlternateSetting=1,
                    bNumEndpoints=2,
                    bInterfaceClass=0x0A,
                    bInterfaceSubClass=0x00,
                    bInterfaceProtocol=0x02)
            # There should be exactly one cdc data interface with alternate
            # setting 1.
            if len(interface_with_alternate_setting_1) != 1:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceGenericAssertionError,
                        'Exactly one CDC data interface with alternate setting '
                        '1 should be found.')
            # Check if there are two endpoint descriptors.
            if interface_with_alternate_setting_1[0].bNumEndpoints != 2:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceAssertionError,
                        'Number of endpoints should be two.')

            # Check the values of fields in endpoint descriptors.
            # There should be one bulk OUT and one bulk IN.
            bulk_in, bulk_out = False, False
            for endpoint in interface_with_alternate_setting_1[0]:
                if (endpoint.bLength == 7 and
                    endpoint.bEndpointAddress < 0x80 and
                    endpoint.bmAttributes == 0x02):
                    bulk_in = True
                elif (endpoint.bLength == 7 and
                      endpoint.bEndpointAddress >= 0x80 and
                      endpoint.bmAttributes == 0x02):
                    bulk_out = True
            if not(bulk_in and bulk_out):
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceGenericAssertionError,
                        'Bulk IN or bulk OUT missing')

            interface_number_with_alternate_setting_1 = (
                    interface_with_alternate_setting_1[0].bInterfaceNumber)

            # MBIM cdc data interface should have both alternate setting 0 and
            # alternate setting 1. Therefore two interface numbers should be
            # the same.
            if (interface_number_with_alternate_setting_0 !=
                    interface_number_with_alternate_setting_1):
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceGenericAssertionError,
                        'MBIM cdc data interface not found')

            mbim_data_interface_number = (
                    interface_number_with_alternate_setting_0)
            # Check the fields of union functional descriptor
            if not(union_functional_descriptor.bLength == 5 and
                   (union_functional_descriptor.bControlInterface ==
                    interface.bInterfaceNumber) and
                   (union_functional_descriptor.bSubordinateInterface0 ==
                    mbim_data_interface_number)):
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceAssertionError,
                        'mbim1.0:6.3#4')

            # Test step 5
            mbim_functional_descriptor_indices = self.descriptor_filter(
                    containers.MBIMFunctionalDescriptor, extra_descriptors)
            mbim_descriptor_index = mbim_functional_descriptor_indices[0]
            if len(mbim_functional_descriptor_indices) > 1:
                for index in mbim_functional_descriptor_indices[1:]:
                    if (extra_descriptors[index] !=
                            extra_descriptors[mbim_descriptor_index]):
                        mbim_errors.log_and_raise(
                                mbim_errors.MBIMComplianceGenericAssertionError,
                                'Unexpected MBIM functional descriptor found')
                        return False

        # End of for interface in interfaces
        return True
    # End of run()


    def descriptor_filter(self, descriptor_type, descriptors):
        """
        Filter a list descriptors based on target descriptor type.

        @param descriptor_type: target descriptor tpye
        @param descriptors: the list of functional descriptors

        @returns a list of the indices of target descriptors
        """
        return [index
                for index, descriptor in enumerate(descriptors)
                if isinstance(descriptor, descriptor_type)]

    #End of descriptor_filter()
