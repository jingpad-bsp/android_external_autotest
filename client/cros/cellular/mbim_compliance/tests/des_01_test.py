# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
DES_01 Descriptors Validation for NCM/MBIM Functions

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


class DES_01_Test(test.Test):
    """ Implement the DES_01 Descriptors Validation for NCM/MBIM Functions """

    def __init__(self, test_context):
        self.test_context = test_context


    def run_internal(self):
        """ Run the DES_01 test. """
        # Precondition.
        get_descriptor_sequence.GetDescriptorSequence(self.test_context).run()
        device = self.test_context.device
        if not device:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceTestError,
                                      'Device not found')
        active_configuration = device.get_active_configuration()

        # Test step 1
        # Get interface with alternate setting 0
        interfaces_with_alternate_setting_0 = set(util.find_descriptor(
                active_configuration,
                find_all=True,
                bAlternateSetting=0,
                bNumEndpoints=1,
                bInterfaceClass=0x02,
                bInterfaceSubClass=0x0D))
        if len(interfaces_with_alternate_setting_0) != 1:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceAssertionError,
                                      'mbim1.0:3.2.1#2')
        interface_number_with_alternate_setting_0 = (
                interfaces_with_alternate_setting_0[0].bInterfaceNumber)
        # Get interface with alternate setting 1
        interfaces_with_alternate_setting_1 = set(util.find_descriptor(
                active_configuration,
                find_all=True,
                bAlternateSetting=1,
                bNumEndpoints=1,
                bInterfaceClass=0x02,
                bInterfaceSubClass=0x0E,
                bInterfaceProtocol=0x00))
        if len(interfaces_with_alternate_setting_1) != 1:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceAssertionError,
                                      'mbim1.0:3.2.1#3')
        interface_number_with_alternate_setting_1 = (
                interfaces_with_alternate_setting_1[0].bInterfaceNumber)

        if (interface_number_with_alternate_setting_0 !=
            interface_number_with_alternate_setting_1):
            mbim_errors.log_and_raise(
                    mbim_errors.MBIMComplianceAssertionError,
                    'mbim1.0:3.2.1#1')

        # Test step 2
        # TODO(mcchou): Parsing descriptors is the prerequisite of checking the
        # order between alternate setting 0 and alternate setting 1.

        # Test step 3
        # Get header functinoal descriptor, union functinoal descriptor,
        # MBIM functinoal descriptor and MBIM extended functional
        # descriptor from |interfaces_with_alternate_setting_0[0]|.
        extra_descriptors = utils.get_interface_extra_descriptor(
                interfaces_with_alternate_setting_0[0].extra)
        found_header_functional_descriptor = False
        found_union_functional_descriptor = False
        found_MBIM_functional_descriptor = False
        for descriptor in extra_descriptors:
            if descriptor.bDescriptorSubType == 0x00:
                found_header_functional_descriptor = True
            elif descriptor.bDescriptorSubType == 0x06:
                found_union_functional_descriptor = True
            elif descriptor.bDescriptorSubType == 0x1B:
                found_MBIM_functional_descriptor = True

        if not(found_header_functional_descriptor and
               found_union_functional_descriptor and
               found_MBIM_functional_descriptor):
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceAssertionError,
                                      'mbim1.0:6.3#2')

        # Test step 4
        # Check header funcional descriptor
        header_descriptor_matches = utils.descriptor_filter(
                containers.HeaderFunctionalDescriptor, extra_descriptors)

        if utils.has_distinct_descriptors(header_descriptor_matches):
            mbim_errors.log_and_raise(
                    mbim_errors.MBIMComplianceGenericAssertionError,
                    'Expected 1 unique header functional descriptor.')

        if not(header_functional_descriptor.bDescriptorType == 0x24 and
               header_functional_descriptor.bDescriptorSubtype == 0x00 and
               header_functional_descriptor.bLength == 5 and
               header_functional_descriptor.bcdCDC >= 0x0120):
            mbim_errors.log_and_raise(
                    mbim_errors.MBIMComplianceGenericAssertionError,
                    'Header functional descriptor: wrong value(s)')

        header_descriptor_index, header_functional_descriptor = (
                header_descriptor_matches[0])

        # Test step 5
        # Check union functional descriptor
        union_descriptor_matches = utils.descriptor_filter(
                containers.UnionFunctionalDescriptor, extra_descriptors)
        # If there is more than one union functional descriptor, check if
        # they are the same.
        if utils.has_distinct_descriptors(union_descriptor_matches):
            mbim_errors.log_and_raise(
                    mbim_errors.MBIMComplianceGenericAssertionError,
                    'Expected 1 unique union functional descriptor.')

        union_descriptor_index, union_functional_descriptor = (
                union_descriptor_matches[0])

        if union_descriptor_index < header_descriptor_index:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceAssertionError,
                                      'mbim1.0:6.3#3')

        # Get interface number with alternate setting 0.
        interface_with_alternate_setting_0 = util.find_descriptor(
                active_configuration,
                find_all=True,
                bAlternateSetting=0,
                bNumEndpoints=0,
                bInterfaceClass=0x0A,
                bInterfaceSubClass=0x00,
                bInterfaceProtocol=0x01)

        if len(interface_with_alternate_setting_0) != 1:
            mbim_errors.log_and_raise(
                    mbim_errors.MBIMComplianceAssertionError,
                    'mbim1.0:3.2.2.4#2')

        endpoint_descriptors = [endpoint for endpoint in
                                interface_with_alternate_setting_0[0]]

        if endpoint_descriptors:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceAssertionError,
                                      'mbim1.0:3.2.2.4#4')

        interface_number_with_alternate_setting_0 = (
                interface_with_alternate_setting_0[0].bInterfaceNumber)

        # Get interface with alternate setting 1.
        interface_with_alternate_setting_1 = util.find_descriptor(
                active_configuration,
                find_all=True,
                bAlternateSetting=1,
                bNumEndpoints=2,
                bInterfaceClass=0x0A,
                bInterfaceSubClass=0x00,
                bInterfaceProtocol=0x01)

        if len(interface_with_alternate_setting_1) != 1:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceAssertionError,
                                      'mbim1.0:3.2.2.4#2')

        if interface_with_alternate_setting_1[0].bNumEndpoints != 2:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceAssertionError,
                                      'mbim1.0:3.2.2.4#4')

        # Check the values of fields in the endpoint descriptor with
        # alternate setting 1. There should be one bulk OUT and one bulk IN.
        bulk_in, bulk_out = False, False
        for endpoint in interface_with_alternate_setting_1[0]:
            if (endpoint.bLength == 7 and
                endpoint.bEndpointAddress < 0x80 and
                endpoint.bmAttributes == 0x02):
                bulk_out = True
            elif (endpoint.bLength == 7 and
                  endpoint.bEndpointAddress >= 0x80 and
                  endpoint.bmAttributes == 0x02):
                bulk_in = True
        if not (bulk_in and bulk_out):
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceAssertionError,
                                      'mbim1.0:3.2.2.4#4')

        interface_number_with_alternate_setting_1 = (
                interface_with_alternate_setting_1[0].bInterfaceNumber)

        # Get interface with alternate setting 2.
        interface_with_alternate_setting_2 = util.find_descriptor(
                active_configuration,
                find_all=True,
                bAlternateSetting=2,
                bNumEndpoints=2,
                bInterfaceClass=0x0A,
                bInterfaceSubClass=0x00,
                bInterfaceProtocol=0x02)

        if len(interface_with_alternate_setting_2) != 1:
           mbim_errors.log_and_raise(mbim_errors.MBIMComplianceAssertionError,
                                     'mbim1.0:3.2.2.4#3')

        if interface_with_alternate_setting_2[0].bNumEndpoints != 2:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceAssertionError,
                                      'mbim1.0:3.2.2.4#4')
        # Check the values of fields in the endpoint descriptor with
        # alternate setting 2. There should be one bulk OUT and one bulk IN.
        bulk_in, bulk_out = False, False
        for endpoint in interface_with_alternate_setting_2[0]:
            if (endpoint.bLength == 7 and
                endpoint.bEndpointAddress < 0x80 and
                endpoint.bmAttributes == 0x02):
                bulk_out = True
            elif (endpoint.bLength == 7 and
                  endpoint.bEndpointAddress >= 0x80 and
                  endpoint.bmAttributes == 0x02):
                bulk_in = True
        if not(bulk_in and bulk_out):
            mbim_errors.log_and_raise(
                    mbim_errors.MBIMComplianceAssertionError,
                    'mbim1.0:3.2.2.4#4')
        interface_number_with_alternate_setting_2 = (
                interface_with_alternate_setting_2[0].bInterfaceNumber)

        if not(interface_number_with_alternate_setting_0 ==
               interface_number_with_alternate_setting_1 ==
               interface_number_with_alternate_setting_2):
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceAssertionError,
                                      'mbim1.0:3.2.2.4#1')

        if not(union_functional_descriptor.bLength == 5 and
               union_functional_descriptor.bControlInterface == (
                       interfaces_with_alternate_setting_0[0].bInterfaceNumber)
               and
               union_functional_descriptor.bSubordinateInterface0 == (
                       interface_number_with_alternate_setting_0)):
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceAssertionError,
                                      'mbim1.0:6.3#4')
        #TODO(mcchou): Continue the remaining test steps.
    # End of run_internal()
