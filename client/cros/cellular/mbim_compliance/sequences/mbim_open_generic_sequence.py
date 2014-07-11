# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
MBIM Open Generic Sequence

Reference:
    [1] Universal Serial Bus Communication Class MBIM Compliance Testing: 19
        http://www.usb.org/developers/docs/devclass_docs/MBIM-Compliance-1.0.pdf
"""
import struct
import array
from usb import core

import common
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_channel
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_control
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_errors
from autotest_lib.client.cros.cellular.mbim_compliance import test_context
from autotest_lib.client.cros.cellular.mbim_compliance import usb_descriptors
from autotest_lib.client.cros.cellular.mbim_compliance.sequences \
        import get_descriptors_sequence
from autotest_lib.client.cros.cellular.mbim_compliance.sequences \
        import open_sequence


class MBIMOpenGenericSequence(open_sequence.OpenSequence):
    """ Implement the MBIM Open Generic Sequence. """

    def __init__(self, test_context):
        """
        @param test_context: An object that wraps information about the device
               under test.
        """
        self.test_context = test_context


    def run_internal(self):
        """ Run the MBIM Open Generic Sequence. """
        # Step 1
        # TODO(mcchou): This step will be removed once mbim functional
        #               descriptor and endpoint descriptors are stashed to
        #               test_context.py.
        descriptors = get_descriptors_sequence.GetDescriptorsSequence(
                self.test_context).run()
        # Step 2
        # Find communication interface and data interface for MBIM only function
        mbim_found, ncm_mbim_found = False, False
        if self.test_context.device_type == test_context.DEVICE_TYPE_MBIM:
            mbim_communication_interface = (
                    self.test_context.mbim_communication_interface)
            no_data_data_interface = self.test_context.no_data_data_interface
            mbim_data_interface = self.test_context.mbim_data_interface
            mbim_found = True
        elif self.test_context.device_type == test_context.DEVICE_TYPE_NCM_MBIM:
            mbim_communication_interface = (
                    self.test_context.mbim_communication_interface)
            ncm_communication_interface = (
                    self.test_context.ncm_communication_interface)
            no_data_data_interface = self.test_context.no_data_data_interface
            ncm_data_interface = self.test_context.ncm_data_interface
            mbim_data_interface = self.test_context.mbim_data_interface
            ncm_mbim_found = True
        else:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceFrameworkError,
                                      'No MBIM or NCM/MBIM function found.')

        communication_interface_number = (
                mbim_communication_interface.bInterfaceNumber)
        data_interface_number = mbim_data_interface.bInterfaceNumber

        # Step 3
        # Set alternate setting to be 0 for MBIM only data interface and
        # NCM/MBIM data interface.
        self.detach_kernel_driver_if_active(data_interface_number)
        self.set_alternate_setting(data_interface_number, 0)

        # Step 4
        # Set alternate setting to be 1 for MBIM communication interface of
        # NCM/MBIM function.
        if ncm_mbim_found:
            self.set_alternate_setting(communication_interface_number, 1)

        # Step 5
        # Send a RESET_FUNCTION(0x05) request to reset communication interface.
        self.reset_function(communication_interface_number)

        # Step 6
        # Send GetNtbParameters() request to communication interface.
        ntb_parameters = self.get_ntb_parameters(
                mbim_communication_interface.bInterfaceNumber)

        # Step 7
        # Send SetNtbFormat() request to communication interface.
        # Bit 1 of |bmNtbForatsSupported| indicates whether the device uses
        # 16-bit or 32-bit NTBs
        if (ntb_parameters.bmNtbFormatsSupported>>1) & 1:
            self.set_ntb_format(communication_interface_number,
                                open_sequence.NTB_32)

        # Step 8
        # Send SetNtbInputSize() request to communication interface.
        self.set_ntb_input_size(communication_interface_number,
                                ntb_parameters.dwNtbInMaxSize)

        # Step 9
        # Send SetMaxDatagramSize() request to communication interface.
        mbim_communication_interface_bundle = (
                usb_descriptors.get_descriptor_bundle(
                        descriptors, mbim_communication_interface))
        # TODO(mcchou): Stash |mbim_functional_descriptor| to test_context.py.
        mbim_functional_descriptors = (
                usb_descriptors.filter_descriptors(
                        usb_descriptors.MBIMFunctionalDescriptor,
                        mbim_communication_interface_bundle))
        if len(mbim_functional_descriptors) != 1:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceSequenceError,
                                      'Expected 1 MBIM functional descriptor.')

        mbim_functional_descriptor = mbim_functional_descriptors[0]
        # Bit 3 determines whether the device can process SetMaxDatagramSize()
        # and GetMaxDatagramSize() requests.
        if (mbim_functional_descriptor.bmNetworkCapabilities>>3) & 1:
            self.set_max_datagram_size(communication_interface_number)

        # Step 10
        if mbim_found:
            alternate_setting = 1
        else:
            alternate_setting = 2
        self.set_alternate_setting(data_interface_number, alternate_setting)

        # Step 11 and 12
        # Send MBIM_OPEN_MSG request and receive the response.
        # TODO(mcchou): Stash |interrupt_endpoint| to test_context.py.
        interrupt_endpoint = (
                usb_descriptors.filter_descriptors(
                        usb_descriptors.EndpointDescriptor,
                        mbim_communication_interface_bundle))
        interrupt_endpoint_address = interrupt_endpoint[0].bEndpointAddress
        """
        packet_generator = (
                mbim_control.PacketGenerator(
                        mbim_control.MBIM_OPEN_MSG,
                        mbim_functional_descriptor.wMaxControlMessage))
        packets = packet_generator.generate_packets()
        """
        # TODO(mcchou): For unblocking the CM_xx tests. A new version of
        #               message contructing will be presented.
        packets = [array.array('B',
                [1, 0, 0, 0, 16, 0, 0, 0, 1, 0, 0, 0, 0, 6, 0, 0])]
        device_filter = {'idVendor': self.test_context.id_vendor,
                         'idProduct': self.test_context.id_product}

        # TODO(mcchou): Come up with a way to release the device.
        #device_copy = self.test_context.device
        del self.test_context._device

        channel = mbim_channel.MBIMChannel(
                device_filter,
                communication_interface_number,
                interrupt_endpoint_address,
                mbim_functional_descriptor.wMaxControlMessage)

        response_packets = channel.bidirectional_transaction(*packets)
        channel.close()

        # TODO(mcchou): Remove the code after we hava a better solution.
        self.test_context._device = core.find(
                idVendor=self.test_context.id_vendor,
                idProduct=self.test_context.id_product)

        # Step 13
        # Verify if MBIM_OPEN_MSG request succeeds.

        # TODO(mcchou): For unblocking the CM_xx tests. A new version of
        #               message contructing will be presented.
        response_packet = response_packets[0]
        status_codes = struct.unpack_from(
                '<I', response_packet.tostring(), offset=12)

        if status_codes[0] != mbim_control.MBIM_STATUS_SUCCESS:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceSequenceError,
                                      'MBIM_OPEN_MSG request failed.')

    # end of run_internal()
