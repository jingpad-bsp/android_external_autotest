# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import unittest
import array

import common
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_data
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_errors


class MBIMDataTestCase(unittest.TestCase):
    """ Test cases for verifying |InformationBuffer| functionality. """

    def test_information_buffer_creation(self):
        """
        Verifies that the |InformationBuffer| object is created correctly.
        """
        data = mbim_data.MBIMDeviceCapsInfoStructure(
                device_type=1,
                cellular_class=2,
                voice_class=3,
                sim_class=4,
                data_class=5,
                sms_caps=6,
                control_caps=7,
                max_sessions=8,
                custom_data_class_offset=9,
                custom_data_class_size=10,
                device_id_offset=11,
                device_id_size=12,
                firmware_info_offset=13,
                firmware_info_size=14,
                hardware_info_offset=15,
                hardware_info_size=16,
                data_buffer=array.array('B', [0x01, 0x02, 0x03, 0x04]))
        byte_array = data.pack()
        expected_byte_array = array.array('B', [
                0x01, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x03, 0x00,
                0x00, 0x00, 0x04, 0x00, 0x00, 0x00, 0x05, 0x00, 0x00, 0x00,
                0x06, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00, 0x08, 0x00,
                0x00, 0x00, 0x09, 0x00, 0x00, 0x00, 0x0A, 0x00, 0x00, 0x00,
                0x0B, 0x00, 0x00, 0x00, 0x0C, 0x00, 0x00, 0x00, 0x0D, 0x00,
                0x00, 0x00, 0x0E, 0x00, 0x00, 0x00, 0x0F, 0x00, 0x00, 0x00,
                0x10, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04])
        self.assertEqual(data.device_type, 1)
        self.assertEqual(data.cellular_class, 2)
        self.assertEqual(data.voice_class, 3)
        self.assertEqual(data.sim_class, 4)
        self.assertEqual(data.data_class, 5)
        self.assertEqual(data.sms_caps, 6)
        self.assertEqual(data.control_caps, 7)
        self.assertEqual(data.max_sessions, 8)
        self.assertEqual(data.custom_data_class_offset, 9)
        self.assertEqual(data.custom_data_class_size, 10)
        self.assertEqual(data.device_id_offset, 11)
        self.assertEqual(data.device_id_size, 12)
        self.assertEqual(data.firmware_info_offset, 13)
        self.assertEqual(data.firmware_info_size, 14)
        self.assertEqual(data.hardware_info_offset, 15)
        self.assertEqual(data.hardware_info_size, 16)
        self.assertEqual(byte_array, expected_byte_array)


    def test_argument_mismatch_for_infomation_buffer_structure(self):
        """
        An exception should be raised if there is any unknown argument.

        Verifies that an exveption is raised when there is any argument which is
        not defined in the information buffer structure.
        """
        with self.assertRaisesRegexp(
                mbim_errors.MBIMComplianceControlMessageError,
                '^Unknown field\(s\) (.*) found in arguments for '
                'MBIMRadioStateInfoStructure\.$'):
            mbim_data.MBIMRadioStateInfoStructure(unknown_field=1)


    def test_missing_field_for_creating_information_buffer_structure(self):
        """
        An exception should be raised if any required field is None.

        Verifies that an exception is raised when None is found in the required
        fields. None is not allowed while creating packets.
        """
        with self.assertRaisesRegexp(
                mbim_errors.MBIMComplianceControlMessageError,
                '^Field hw_radio_state is required to create a '
                'MBIMRadioStateInfoStructure\.$'):
            mbim_data.MBIMRadioStateInfoStructure(hw_radio_state=None)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
