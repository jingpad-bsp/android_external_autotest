# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# This module contains unit tests for the classes in the mtb module

import os
import unittest

import common_unittest_utils
import mtb

# Include some constants
execfile('firmware_constants.py', globals())


def get_mtb_packets(gesture_filename):
    """Get mtb_packets object by reading the gesture file."""
    parser = mtb.MTBParser()
    packets = parser.parse_file(gesture_filename)
    mtb_packets = mtb.MTB(packets)
    return mtb_packets


class FakeMTB(mtb.MTB):
    """A fake MTB class to set up x and y positions directly."""
    def __init__(self, list_x, list_y):
        self.list_x = list_x
        self.list_y = list_y

    def get_x_y(self, target_slot):
        """Return list_x, list_y directly."""
        return (self.list_x, self.list_y)


class MTBTest(unittest.TestCase):
    """Unit tests for mtb.MTB class."""

    def setUp(self):
        self.test_dir = os.path.join(os.getcwd(), 'tests')
        self.data_dir = os.path.join(self.test_dir, 'data')

    def _get_filepath(self, filename):
        return os.path.join(self.data_dir, filename)

    def _call_get_reversed_motions(self, list_x, list_y, expected_x,
                                   expected_y, direction):
        mtb = FakeMTB(list_x, list_y)
        displacement = mtb.get_reversed_motions(0, direction)
        self.assertEqual(displacement[X], expected_x)
        self.assertEqual(displacement[Y], expected_y)

    def test_get_reversed_motions_no_reversed(self):
        list_x = (10, 22 ,36, 54, 100)
        list_y = (1, 2 ,6, 10, 22)
        self._call_get_reversed_motions(list_x, list_y, 0, 0, DIAGONAL)

    def test_get_reversed_motions_reversed_x_y(self):
        list_x = (10, 22 ,36, 154, 100)
        list_y = (1, 2 ,6, 30, 22)
        self._call_get_reversed_motions(list_x, list_y, -54, -8, DIAGONAL)

    def _test_get_x_y(self, filename, slot, expected_value):
        gesture_filename = self._get_filepath(filename)
        mtb_packets = get_mtb_packets(gesture_filename)
        list_x, list_y = mtb_packets.get_x_y(slot)
        points = zip(list_x, list_y)
        self.assertEqual(len(points), expected_value)

    def test_get_x_y(self):
        self._test_get_x_y('one_finger_with_slot_0.dat', 0, 12)
        self._test_get_x_y('one_finger_without_slot_0.dat', 0, 9)
        self._test_get_x_y('two_finger_with_slot_0.dat', 0, 121)
        self._test_get_x_y('two_finger_with_slot_0.dat', 1, 59)
        self._test_get_x_y('two_finger_without_slot_0.dat', 0, 104)
        self._test_get_x_y('two_finger_without_slot_0.dat', 1, 10)

    def test_get_x_y_multiple_slots(self):
        filename = 'x_y_multiple_slots.dat'
        filepath = self._get_filepath(filename)
        mtb_packets = get_mtb_packets(filepath)
        slots = (0, 1)
        list_x, list_y = mtb_packets.get_x_y_multiple_slots(slots)
        expected_list_x = {}
        expected_list_y = {}
        expected_list_x[0] = [1066, 1068, 1082, 1183, 1214, 1285, 1322, 1351,
                              1377, 1391]
        expected_list_y[0] = [561, 559, 542, 426, 405, 358, 328, 313, 304, 297]
        expected_list_x[1] = [770, 769, 768, 758, 697, 620, 585, 565, 538, 538]
        expected_list_y[1] = [894, 894, 895, 898, 927, 968, 996, 1003, 1013,
                              1013]
        for slot in slots:
            self.assertEqual(list_x[slot], expected_list_x[slot])
            self.assertEqual(list_y[slot], expected_list_y[slot])

    def _test_get_points_for_every_tracking_id(self, filename, expected_values):
        gesture_filename = self._get_filepath(filename)
        mtb_packets = get_mtb_packets(gesture_filename)
        points = mtb_packets.get_points_for_every_tracking_id()
        for tracking_id in expected_values:
            self.assertEqual(len(points[tracking_id]),
                             expected_values[tracking_id])

    def test_get_points_for_every_tracking_id(self):
        self._test_get_points_for_every_tracking_id(
                'two_finger_with_slot_0.dat', {2101: 121, 2102: 59})
        self._test_get_points_for_every_tracking_id(
                'two_finger_without_slot_0.dat', {2097: 104, 2098: 10})

    def _test_drumroll(self, filename, check_func):
        gesture_filename = self._get_filepath(filename)
        mtb_packets = get_mtb_packets(gesture_filename)
        max_distance = mtb_packets.get_max_distance_of_all_tracking_ids()
        self.assertTrue(check_func(max_distance))

    def test_drumroll(self):
        check_func = lambda x: x >= 50
        self._test_drumroll('drumroll_lumpy.dat', check_func)

    def test_drumroll1(self):
        check_func = lambda x: x >= 50
        self._test_drumroll('drumroll_lumpy_1.dat', check_func)

    def test_drumroll_link(self):
        check_func = lambda x: x >= 50
        self._test_drumroll('drumroll_link.dat', check_func)

    def test_no_drumroll_link(self):
        check_func = lambda x: x <= 20
        self._test_drumroll('no_drumroll_link.dat', check_func)

    def test_no_drumroll_link(self):
        check_func = lambda x: x >= 50
        self._test_drumroll('drumroll_link_2.dat', check_func)

    def test_get_points_for_every_tracking_id2(self):
        gesture_filename = self._get_filepath('drumroll_link_2.dat')
        mtb_packets = get_mtb_packets(gesture_filename)
        points = mtb_packets.get_points_for_every_tracking_id()
        list_95 = [(789, 358), (789, 358), (789, 358), (789, 358), (789, 358),
                   (789, 359), (789, 359), (789, 359), (788, 359), (788, 360),
                   (788, 360), (787, 360), (787, 361), (490, 903), (486, 892),
                   (484, 895), (493, 890), (488, 893), (488, 893), (489, 893),
                   (490, 893), (490, 893), (491, 893), (492, 893)]
        list_104 = [(780, 373), (780, 372), (780, 372), (780, 372), (780, 373),
                    (780, 373), (781, 373)]
        for pa, pb in zip(list_95, points[95]):
            self.assertEqual(pa, pb)
        for pa, pb in zip(list_104, points[104]):
            self.assertEqual(pa, pb)
        self.assertTrue(True)

    def test_convert_to_evemu_format(self):
        evemu_filename = self._get_filepath('one_finger_swipe.evemu.dat')
        mtplot_filename = self._get_filepath('one_finger_swipe.dat')
        packets = mtb.MTBParser().parse_file(mtplot_filename)
        evemu_converted_iter = iter(mtb.convert_to_evemu_format(packets))
        with open(evemu_filename) as evemuf:
            for line_evemu_original in evemuf:
                evemu_original = line_evemu_original.split()
                evemu_converted_str = next(evemu_converted_iter, None)
                self.assertNotEqual(evemu_converted_str, None)
                if evemu_converted_str:
                    evemu_converted = evemu_converted_str.split()
                self.assertEqual(len(evemu_original), 5)
                self.assertEqual(len(evemu_converted), 5)
                # Skip the timestamps for they are different in both formats.
                # Prefix, type, code, and value should be the same.
                for i in [0, 2, 3, 4]:
                    self.assertEqual(evemu_original[i], evemu_converted[i])



if __name__ == '__main__':
  unittest.main()
