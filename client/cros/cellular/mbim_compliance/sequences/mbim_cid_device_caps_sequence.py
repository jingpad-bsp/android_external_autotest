# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
MBIM_CID_DEVICE_CAPS Sequence

Reference:
    [1] Universal Serial Bus Communication Class MBIM Compliance Testing: 22
        http://www.usb.org/developers/docs/devclass_docs/MBIM-Compliance-1.0.pdf
"""
import common
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_channel
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_control
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_errors
from autotest_lib.client.cros.cellular.mbim_compliance.sequences \
        import sequence


class MBIMCIDDeviceCapsSequence(sequence.Sequence):
    """ Implement |MBIMCIDDeviceCapsSequence|. """

    def run_internal(self):
        """ Run the MBIM_CID_DEVICE_CAPS Sequence. """
        # Step 1
        # Send MBIM_COMMAND_MSG.
        command_message = mbim_control.MBIMCommandMessage(
                device_service_id=mbim_control.UUID_BASIC_CONNECT.bytes,
                cid=mbim_control.MBIM_CID_DEVICE_CAPS,
                command_type=mbim_control.COMMAND_TYPE_QUERY,
                information_buffer_length=0)
        packets = command_message.generate_packets()
        channel = mbim_channel.MBIMChannel(
                {'idVendor': self.test_context.id_vendor,
                 'idProduct': self.test_context.id_product},
                self.test_context.mbim_communication_interface.bInterfaceNumber,
                self.test_context.interrupt_endpoint.bEndpointAddress,
                self.test_context.mbim_functional.wMaxControlMessage)
        response_packets = channel.bidirectional_transaction(*packets)
        channel.close()

        # Step 2
        response_message = mbim_control.parse_response_packets(response_packets)

        # Step 3
        if (response_message.message_type != mbim_control.MBIM_COMMAND_DONE or
            response_message.status_codes != mbim_control.MBIM_STATUS_SUCCESS):
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceAssertionError,
                                      'mbim1.0:9.4.3')

        return command_message, response_message
