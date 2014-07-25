# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import unittest
import array

import common
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_constants
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_control
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_errors


class MBIMControlTestCase(unittest.TestCase):
    """
    Test cases for verifying |MBIMMessageBase| functionality and the
    |parse_response_packets| method.
    """
    def test_argument_mismatch_for_control_message_consturctor(self):
        """
        Verifies that an exception is raised when where is any argument which is
        not definded in the control message classes.
        """
        with self.assertRaisesRegexp(
                mbim_errors.MBIMComplianceControlMessageError,
                '^Unknown field\(s\) (.*) found in arguments for '
                'MBIMOpenMessage\.$'):
            open_message = mbim_control.MBIMOpenMessage(x=0, y=1)


    def test_missing_field_for_creating_control_message(self):
        """
        Verifies that an exception is raised when the valuse(s) of the required
        field(s) is None.
        """
        with self.assertRaisesRegexp(
                mbim_errors.MBIMComplianceControlMessageError,
                '^Field (.*) is required to create a MBIMOpenMessage\.$'):
            open_message = mbim_control.MBIMOpenMessage()


    def test_success_of_packet_generating(self):
        """
        Verifies that packets for the open message is generated correctly using
        |generate_packets|.
        """
        open_message = mbim_control.MBIMOpenMessage(max_control_transfer=1536)
        expected_packets = [array.array('B',
                [0x01, 0x00, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x01, 0x00,
                 0x00, 0x00, 0x00, 0x06, 0x00, 0x00])]
        actual_packets = open_message.generate_packets()
        # Compare message_type and message_length.
        # expected_message_type = expected_packets[:4]
        # expected_message_length = expected_packets[4:8]
        # expected_max_control_transf
        self.assertEqual(expected_packets[0][0:8], actual_packets[0][0:8])
        # Skip transaction_id and compare max_control_transfer.
        self.assertEqual(expected_packets[0][12:], actual_packets[0][12:])


    def test_no_packets_to_parse(self):
        """
        Verifies that an exception wi raised when there is no packets to be
        parsed.
        """
        packets = []
        with self.assertRaisesRegexp(
                mbim_errors.MBIMComplianceControlMessageError,
                '^Expected at least 1 packet to parse, got 0\.$'):
            mbim_control.parse_response_packets(packets)


    def test_parsing_packets_with_insufficient_length_for_header(self):
        """
        Verifies that an exception is raised when the length of the first packet
        is less than the length of a |MBIMHeader|.
        """
        packets = [array.array('B', [1])]
        with self.assertRaisesRegexp(
                mbim_errors.MBIMComplianceControlMessageError,
                '^The length of the packet should be at least 12 for '
                'MBIMHeader, got 1\.$'):
            mbim_control.parse_response_packets(packets)


    def test_parsing_packets_with_insufficient_length_for_message(self):
        """
        Verifies that an exception is raised when the length of the first packet
        is less the the length required for the response message.
        """
        packets = [array.array('B', [0x01, 0x00, 0x00, 0x80, 0x0d, 0x00, 0x00,
                                     0x00, 0x01, 0x00, 0x00, 0x00, 0x01])]
        with  self.assertRaisesRegexp(
                mbim_errors.MBIMComplianceControlMessageError,
                '^The length of the packet should be at least 16 for (.*), '
                'got 13\.$'):
            mbim_control.parse_response_packets(packets)


    def test_parsing_continuation_packet_with_insufficient_length(self):
        """
        Verifies that an exception is raised when the length of the continuation
        packet is less then the total length of |MBIMHeader| and
        |MBIMFragmentHeader|.
        """
        packets = [array.array('B', [0x03, 0x00, 0x00, 0x80, 0x03, 0x04, 0x00,
                                     0x00, 0x01, 0x00, 0x00, 0x00, 0x02, 0x00,
                                     0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                                     0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                                     0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                                     0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00,
                                     0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01,
                                     0x01, 0x01, 0x01]),
                   array.array('B', [0x01])]

        with self.assertRaisesRegexp(
                mbim_errors.MBIMComplianceControlMessageError,
                '^The length of the continuation packet\(s\) for (.*) should '
                'be at least 20\.$'):
            mbim_control.parse_response_packets(packets)


    def test_success_of_parsing_mbim_open_done(self):
        """
        Verifies the packets of |MBIM_OPEN_DONE| type are parsed correctly.
        """
        packets = [array.array('B', [0x01, 0x00, 0x00, 0x80, 0x10, 0x00, 0x00,
                                     0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00,
                                     0x00, 0x00])]
        message = mbim_control.parse_response_packets(packets)
        self.assertEqual(message.message_type, mbim_constants.MBIM_OPEN_DONE)
        self.assertEqual(message.message_length, 16)
        self.assertEqual(message.transaction_id, 1)
        self.assertEqual(message.status_codes,
                         mbim_constants.MBIM_STATUS_SUCCESS)


    def test_success_of_parsing_mbim_close_done(self):
        """
        Verifies the packets of |MBIM_OPEN_DONE| type are parsed correctly.
        """
        packets = [array.array('B', [0x02, 0x00, 0x00, 0x80, 0x10, 0x00, 0x00,
                                     0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00,
                                     0x00, 0x00])]
        message = mbim_control.parse_response_packets(packets)
        self.assertEqual(message.message_type, mbim_constants.MBIM_CLOSE_DONE)
        self.assertEqual(message.message_length, 16)
        self.assertEqual(message.transaction_id, 1)
        self.assertEqual(message.status_codes,
                         mbim_constants.MBIM_STATUS_SUCCESS)


    def test_success_of_parsing_mbim_command_done(self):
        """
        Verifies the packets of |MBIM_COMMAND_DONE| type are parsed correctly.
        """
        packets = [array.array('B', [0x03, 0x00, 0x00, 0x80, 0x34, 0x00, 0x00,
                                     0x00, 0x01, 0x00, 0x00, 0x00, 0x02, 0x00,
                                     0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                                     0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                                     0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                                     0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00,
                                     0x00, 0x00, 0x08, 0x00, 0x00, 0x00, 0x01,
                                     0x01, 0x01, 0x01]),
                   array.array('B', [0x03, 0x00, 0x00, 0x80, 0x18, 0x00, 0x00,
                                     0x00, 0x01, 0x00, 0x00, 0x00, 0x02, 0x00,
                                     0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
                                     0x01, 0x01, 0x01])]
        message = mbim_control.parse_response_packets(packets)

        self.assertEqual(message.message_type, mbim_constants.MBIM_COMMAND_DONE)
        self.assertEqual(message.message_length, 52)
        self.assertEqual(message.transaction_id, 1)
        self.assertEqual(message.total_fragments, 2)
        self.assertEqual(message.current_fragment, 0)
        self.assertEqual(message.device_service_id,
                         '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                         '\x00\x00\x00\x00')
        self.assertEqual(message.cid, 1)
        self.assertEqual(message.status_codes,
                         mbim_constants.MBIM_STATUS_SUCCESS)
        self.assertEqual(message.information_buffer_length, 8)
        self.assertEqual(message.information_buffer,
                         array.array('B', [0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
                                           0x01, 0x01]))


    def test_success_of_parsing_mbim_function_error_msg(self):
        """
        Verifies the |MBIM_FUNCTION_ERROR_MSG| packets are parsed correctly.
        """
        packets = [array.array('B', [0x04, 0x00, 0x00, 0x80, 0x10, 0x00, 0x00,
                                     0x00, 0x01, 0x00, 0x00, 0x00, 0x06, 0x00,
                                     0x00, 0x00])]
        message = mbim_control.parse_response_packets(packets)
        self.assertEqual(message.message_type,
                         mbim_constants.MBIM_FUNCTION_ERROR_MSG)
        self.assertEqual(message.message_length, 16)
        self.assertEqual(message.transaction_id, 1)
        self.assertEqual(message.error_status_code,
                         mbim_constants.MBIM_ERROR_UNKNOWN)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
