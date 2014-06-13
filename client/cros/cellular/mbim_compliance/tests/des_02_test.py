# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
DES_02 Descriptors Validation for MBIM Only Functions

Reference:
    [1] Universal Serial Bus Communication Class MBIM Compliance Testing: 26
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
        """ Run the DES_02 test. """
        # Precondition.
        get_descriptor_sequence.GetDescriptorSequence(self.test_context).run()
        device = self.test_context.device
        if not device:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceTestError,
                                      'Device not found')
        active_configuration = device.get_active_configuration()

        # Test step 1
        interfaces = util.find_descriptor(active_configuration,
                                          find_all=True,
                                          bAlternateSetting=0,
                                          bNumEndpoints=1,
                                          bInterfaceClass=0x02,
                                          bInterfaceSubClass=0x0E,
                                          bInterfaceProtocol=0x00)
        if not interfaces:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceAssertionError,
                                      'mbim1.0:6.3#1')

        for interface in interfaces:
            # Test step 2
            # Get header functional descriptor, union functional descriptor,
            # MBIM functional descriptor and MBIM extended functional
            # descriptor.
            extra_descriptors = utils.get_interface_extra_descriptors(
                   interface.extra)
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
            # Check header functional descriptor.
            header_descriptor_matches = utils.descriptor_filter(
                    containers.HeaderFunctionalDescriptor, extra_descriptors)

            if utils.has_distinct_descriptors(header_descriptor_matches):
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceGenericAssertionError,
                        'Expeated 1 unique header functional descriptor.')

            header_descriptor_index, header_functional_descriptor = (
                    header_descriptor_matches[0])

            if not(header_functional_descriptor.bDescriptorType == 0x24 and
                   header_functional_descriptor.bDescriptorSubtype == 0x00 and
                   header_functional_descriptor.bLength == 5 and
                   header_functional_descriptor.bcdCDC >= 0x0120):
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceGenericAssertionError,
                        'Header functional descriptor: wrong value(s)')

            # Test step 4
            # Check union functional descriptor.
            union_descriptor_matches = utils.descriptor_filter(
                    containers.UnionFunctionalDescriptor, extra_descriptors)

            # If there is more than one union functional descriptor, check if
            # they are the same.
            if utils.has_distinct_descriptors(union_descriptor_matches):
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceGenerisAssertionError,
                        'Expected 1 unique union functional descriptor.')

            union_descriptor_index, union_functional_descriptor = (
                    union_descriptor_matches[0])

            if union_descriptor_index < header_descriptor_index:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceAssertionError,
                        'mbim1.0:6.3#3')

            # Get interface numbers with alternate setting 0.
            interface_with_alternate_setting_0 = util.find_descriptor(
                    active_configuration,
                    find_all=True,
                    bAlternateSetting=0,
                    bNumEndpoints=0,
                    bInterfaceClass=0x0A,
                    bInterfaceSubClass=0x00,
                    bInterfaceProtocol=0x02)

            if not interface_with_alternate_setting_0:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceAssertionError,
                        'mbim1.0:6.6#4')
            if len(interface_with_alternate_setting_0) > 1:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceGenericAssertionError,
                        'Exactly 1 CDC data interface with alternate setting 0 '
                        'should be found.')
            endpoint_descriptors = [
                    endpoint for endpoint in
                            interface_with_alternate_setting_0[0]]
            if endpoint_descriptors:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceAssertionError,
                        'mbim1.0:6.6#2')

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

            if not interface_with_alternate_setting_1:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceAssertionError,
                        'mbim1.0:6.6#4')
            # There should be exactly one cdc data interface with alternate
            # setting 1.
            if len(interface_with_alternate_setting_1) > 1:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceGenericAssertionError,
                        'Expected 1 CDC data interface with alternate setting '
                        '1.')
            # Check if there are two endpoint descriptors.
            if interface_with_alternate_setting_1[0].bNumEndpoints != 2:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceAssertionError,
                        'mbim1.0:6.6#3.')
            # Check the values of fields in endpoint descriptors.
            # There should be one bulk OUT and one bulk IN.
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
            if not(bulk_in and bulk_out):
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceAssertionError,
                        'mbim1.0:6.6#3')

            interface_number_with_alternate_setting_1 = (
                    interface_with_alternate_setting_1[0].bInterfaceNumber)

            # MBIM cdc data interface should have both alternate setting 0 and
            # alternate setting 1. Therefore two interface numbers should be
            # the same.
            if (interface_number_with_alternate_setting_0 !=
                    interface_number_with_alternate_setting_1):
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceAssertionError,
                        'mbim1.0:6.6#1')

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
            # Get MBIM functional descriptor.
            mbim_descriptor_matches = utils.descriptor_filter(
                    containers.MBIMFunctionalDescriptor, extra_descriptors)

            # If there is more then one MBIM functional descriptor, check if
            # they are the same.
            if utils.has_distinct_descriptors(mbim_descriptor_matches):
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceGenericAssertionError,
                        'Expected 1 unique MBIM functional descriptor.')

            mbim_descriptor_index, mbim_functional_descriptor = (
                    mbim_descriptor_matches[0])

            if mbim_functional_descriptor.bLength != 12:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceAssertionError,
                        'mbim1.0:6.4#5')

            if mbim_functional_descriptor.bcdMBIMVersion != 0x0100:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceAssertionError,
                        'mbim1.0:6.4#6')

            if mbim_functional_descriptor.wMaxControlMessage < 64:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceAssertionError,
                        'mbim1.0:6.4#1')

            if mbim_functional_descriptor.bNumberFilters < 16:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceAssertionError,
                        'mbim1.0:6.4#2')

            if mbim_functional_descriptor.bMaxFilterSize > 192:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceAssertionError,
                        'mbim1.0:6.4#3')

            # TODO(mcchou): Most of vendors set wMaxSegmentSize to be less than
            # 1500, so this assertion is skipped for now.
            #
            #if not mbim_functional_descriptor.wMaxSegmentSize >= 2048:
            #    mbim_errors.log_and_raise(
            #            mbim_errors.MBIMComplianceAssertionError,
            #            'mbim1.0:6.4#4')

            # Use a byte as the mask to check if D0, D1, D2, D4, D6 and D7 are
            # zeros.
            if (mbim_functional_descriptor.bmNetworkCapabilities &
                0b11010111) > 0:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceAssertionError,
                        'mbim1.0:6.4#7')

            # Test step 6
            # Get MBIM extended functional descriptor, which is optional.
            mbim_extended_descriptor_matches = (
                    utils.descriptor_filter(
                            containers.MBIMExtendedFunctionalDescriptor,
                            extra_descriptors))

            # If there is more then one MBIM extended functional descriptor,
            # check if they are the same.
            if len(mbim_extended_descriptor_matches) >= 1:
                if utils.has_distinct_descriptors(
                        mbim_extended_descriptor_matches):
                    mbim_errors.log_and_raise(
                            mbim_errors.MBIMComplianceGenerisAssertionError,
                            'Expected 1 unique MBIM extended functional '
                            'descriptor.')

                # Get MBIM extended functional descriptor.
                (mbim_extended_descriptor_index,
                 mbim_extended_functional_descriptor) = (
                        mbim_extended_descriptor_matches[0])

                if mbim_extended_descriptor_index < mbim_descriptor_index:
                    mbim_errors.log_and_raise(
                            mbim_errors.MBIMComplianceAssertionError,
                            'mbim1.0:6.5#1')

                if mbim_extended_functional_descriptor.bLength != 8:
                    mbim_errors.log_and_raise(
                            mbim_errors.MBIMComplianceAssertionError,
                            'mbim1.0:6.5#2')

                if (mbim_extended_functional_descriptor.bcdMBIMEFDVersion !=
                        0x0100):
                    mbim_errors.log_and_raise(
                            mbim_errors.MBIMComplianceAssertionError,
                            'mbim1.0:6.5#3')

                # Get bMaxOutstandingCommandMessages field.
                b_max_outstanding_command_messages = getattr(
                        mbim_extended_functional_descriptor,
                        'bMaxOutstandingCommandMessages')
                if b_max_outstanding_command_messages == 0:
                    mbim_errors.log_and_raise(
                            mbim_errors.MBIMComplianceAssertionError,
                            'mbim1.0:6.5#4')

            # Test step 7
            # Get the first endpoint for current interface.
            endpoint_descriptors = [endpoint for endpoint in interface]
            if len(endpoint_descriptors) != 1:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceGenericAssertionError,
                        'Expected 1 endpoint, got %d.' % (
                                len(endpoint_descriptors)))

            endpoint_descriptor = endpoint_descriptors[0]
            if not (endpoint_descriptor.bDescriptorType == 0x05 and
                    endpoint_descriptor.bLength == 7 and
                    endpoint_descriptor.bEndpointAddress >= 0x80 and
                    endpoint_descriptor.bmAttributes == 0x03):
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceAssertionError,
                        'mbim1.0:6.3#5')

            # TODO(mcchou): All functional descriptors should come before the
            # first endpoint descriptor.

            # Test step 8
            # Get interface association descriptor.
            interface_association_descriptors = (
                    utils.get_configuration_extra_descriptors(
                            active_configuration.extra))
            interface_association_descriptor_matches = utils.descriptor_filter(
                    containers.InterfaceAssociationDescriptor,
                    interface_association_descriptors)

            if utils.has_distinct_descriptors(
                    interface_association_descriptor_matches):
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceGenericAssertionError,
                        'Expected 1 interface association descriptor, got '
                        '%d.' % (len(interface_association_descriptors)))

            interface_association_descriptor = (
                    interface_association_descriptor_matches[0][1])
            # Check interface association descriptor if one of the following
            # condition is met:
            # 1. bFirstInterface <= bControlInterface < (bFirstInterface +
            #                                            bInterfaceCount)
            # 2. bFirstInterface <= bSubordinateInterface0 < (bFirstInterface +
            #                                                 bInterfaceCount)
            b_first_interface = (
                    interface_association_descriptor.bFirstInterface)
            b_interface_count = (
                    interface_association_descriptor.bInterfaceCount)
            b_control_interface = (
                    union_functional_descriptor.bControlInterface)
            b_subordinate_interface_0 = (
                    union_functional_descriptor.bSubordinateInterface0)
            check_inteface_association_descriptor = False

            if ((b_first_interface <= b_control_interface < (b_first_interface +
                        b_interface_count)) or
                (b_first_interface <= b_subordinate_interface_0 < (
                        b_first_interface + b_interface_count))):
                check_interface_association_descriptor = True

            if not check_interface_association_descriptor:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceAssertionError,
                        'mbim1.0:6.1#1')

            if check_interface_association_descriptor:
                if not((b_first_interface == b_control_interface or
                        b_first_interface == b_subordinate_interface_0) and
                       (b_interface_count == 2) and
                       (b_subordinate_interface_0 == b_control_interface + 1 or
                        b_subordinate_interface_0 == b_control_interface - 1)
                       and
                       (interface_association_descriptor.bFunctionClass ==
                        0x02) and
                       (interface_association_descriptor.bFunctionSubClass ==
                        0x0E) and
                       (interface_association_descriptor.bFunctionProtocol ==
                        0x00)):
                    mbim_errors.log_and_raise(
                            mbim_errors.MBIMComplianceAssertionError,
                            'mbim1.0:6.1#2')

        # End of for interface in interfaces
    # End of run_internal()
