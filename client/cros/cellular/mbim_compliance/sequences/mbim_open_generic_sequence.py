# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
MBIM Open Generic Sequence

Reference:
    [1] Universal Serial Bus Communication Class MBIM Compliance Testing: 19
        http://www.usb.org/developers/docs/devclass_docs/MBIM-Compliance-1.0.pdf
"""
from usb import core

import common
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_channel
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_control
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_errors
from autotest_lib.client.cros.cellular.mbim_compliance import test_context
from autotest_lib.client.cros.cellular.mbim_compliance.sequences \
        import open_sequence


class MBIMOpenGenericSequence(open_sequence.OpenSequence):
    """ Implement the MBIM Open Generic Sequence. """

    def run_internal(self):
        """ Run the MBIM Open Generic Sequence. """
        # Step 1 and 2
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
        mbim_functional_descriptor = self.test_context.mbim_functional
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
        interrupt_endpoint_address = (
                self.test_context.interrupt_endpoint.bEndpointAddress)

        # TODO(mcchou): For unblocking the CM_xx tests. A new version of
        #               message contructing will be presented.
        max_control_message = (
                mbim_functional_descriptor.wMaxControlMessage)
        open_message = mbim_control.MBIMOpenMessage(
                max_control_transfer=max_control_message)
        packets = open_message.generate_packets()
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
        response_message = mbim_control.parse_response_packets(response_packets)

        if response_message.transaction_id != open_message.transaction_id:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceAssertionError,
                                      'mbim1.0:9.4.1#1')

        if response_message.status_codes != mbim_control.MBIM_STATUS_SUCCESS:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceSequenceError,
                                      'mbim1.0:9.4.1#2')

        return open_message, response_message
