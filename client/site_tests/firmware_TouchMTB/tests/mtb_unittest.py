# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# This module contains unit tests for the classes in the mtb module

import glob
import os
import sys
import unittest

import common_unittest_utils
import fuzzy
import mtb
import test_conf as conf

from firmware_constants import AXIS, GV, MTB, VAL
from geometry.elements import Point, about_eq


def get_mtb_packets(gesture_filename):
    """Get mtb_packets object by reading the gesture file."""
    parser = mtb.MtbParser()
    packets = parser.parse_file(gesture_filename)
    mtb_packets = mtb.Mtb(packets)
    return mtb_packets


class FakeMtb(mtb.Mtb):
    """A fake MTB class to set up x and y positions directly."""
    def __init__(self, list_x, list_y):
        self.list_x = list_x
        self.list_y = list_y

    def get_x_y(self, target_slot):
        """Return list_x, list_y directly."""
        return (self.list_x, self.list_y)


class MtbTest(unittest.TestCase):
    """Unit tests for mtb.Mtb class."""

    def setUp(self):
        self.test_dir = os.path.join(os.getcwd(), 'tests')
        self.data_dir = os.path.join(self.test_dir, 'data')

    def _get_filepath(self, filename, gesture_dir=''):
        return os.path.join(self.data_dir, gesture_dir, filename)

    def _get_range_middle(self, criteria):
        """Get the middle range of the criteria."""
        fc = fuzzy.FuzzyCriteria(criteria)
        range_min , range_max = fc.get_criteria_value_range()
        range_middle = (range_min + range_max) / 2.0
        return range_middle

    def _call_get_reversed_motions(self, list_x, list_y, expected_x,
                                   expected_y, direction):
        mtb = FakeMtb(list_x, list_y)
        displacement = mtb.get_reversed_motions(0, direction, ratio=0.1)
        self.assertEqual(displacement[AXIS.X], expected_x)
        self.assertEqual(displacement[AXIS.Y], expected_y)

    def test_get_reversed_motions_no_reversed(self):
        list_x = (10, 22 ,36, 54, 100)
        list_y = (1, 2 ,6, 10, 22)
        self._call_get_reversed_motions(list_x, list_y, 0, 0, GV.TLBR)

    def test_get_reversed_motions_reversed_x_y(self):
        list_x = (10, 22 ,36, 154, 100)
        list_y = (1, 2 ,6, 30, 22)
        self._call_get_reversed_motions(list_x, list_y, -54, -8, GV.TLBR)

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

    def test_get_x_y_multiple_slots2(self):
        """Test slot state machine.

        When the last slot in the previous packet is slot 0, and the first
        slot in the current packet is also slot 0, the slot 0 will not be
        displayed explicitly. This test ensures that the slot stat machine
        is tracked properly.
        """
        filename = 'pinch_to_zoom.zoom_in.dat'
        filepath = self._get_filepath(filename)
        mtb_packets = get_mtb_packets(filepath)
        slots = (0, 1)
        list_x, list_y = mtb_packets.get_x_y_multiple_slots(slots)
        expected_final_x = {}
        expected_final_y = {}
        expected_final_x[0] = 1318
        expected_final_y[0] = 255
        expected_final_x[1] = 522
        expected_final_y[1] = 1232
        for slot in slots:
            self.assertEqual(list_x[slot][-1], expected_final_x[slot])
            self.assertEqual(list_y[slot][-1], expected_final_y[slot])

    def _test_get_points_for_every_tracking_id(self, filename, expected_values):
        gesture_filename = self._get_filepath(filename)
        mtb_packets = get_mtb_packets(gesture_filename)
        tid_data_dict = mtb_packets.get_points_for_every_tracking_id()
        for tid in expected_values:
            self.assertEqual(len(tid_data_dict[tid].points),
                             expected_values[tid])

    def test_get_points_for_every_tracking_id(self):
        self._test_get_points_for_every_tracking_id(
                'two_finger_with_slot_0.dat', {2101: 121, 2102: 59})
        self._test_get_points_for_every_tracking_id(
                'two_finger_without_slot_0.dat', {2097: 104, 2098: 10})

    def _test_drumroll(self, filename, expected_max_distance):
        """expected_max_distance: unit in pixel"""
        gesture_filename = self._get_filepath(filename)
        mtb_packets = get_mtb_packets(gesture_filename)
        actual_max_distance = mtb_packets.get_max_distance_of_all_tracking_ids()
        self.assertTrue(about_eq(actual_max_distance, expected_max_distance))

    def test_drumroll(self):
        expected_max_distance = 52.0216301167
        self._test_drumroll('drumroll_lumpy.dat', expected_max_distance)

    def test_drumroll1(self):
        expected_max_distance = 43.5660418216
        self._test_drumroll('drumroll_lumpy_1.dat', expected_max_distance)

    def test_drumroll_link(self):
        expected_max_distance = 25.6124969497
        self._test_drumroll('drumroll_link.dat', expected_max_distance)

    def test_no_drumroll_link(self):
        expected_max_distance = 2.91547594742
        self._test_drumroll('no_drumroll_link.dat', expected_max_distance)

    def test_no_drumroll_link(self):
        expected_max_distance = 24.8243831746
        self._test_drumroll('drumroll_link_2.dat', expected_max_distance)

    def test_get_points_for_every_tracking_id2(self):
        gesture_filename = self._get_filepath('drumroll_link_2.dat')
        mtb_packets = get_mtb_packets(gesture_filename)
        tid_data_dict = mtb_packets.get_points_for_every_tracking_id()
        # Check points in two tracking IDs: 95 and 104
        # Tracking ID 95: slot 0 (no explicit slot 0 assigned). This is the
        #                 only slot in the packet.
        list_95 = [(789, 358), (789, 358), (789, 358), (789, 358), (789, 358),
                   (789, 359), (789, 359), (789, 359), (788, 359), (788, 360),
                   (788, 360), (787, 360), (787, 361), (490, 903), (486, 892),
                   (484, 895), (493, 890), (488, 893), (488, 893), (489, 893),
                   (490, 893), (490, 893), (491, 893), (492, 893)]
        # Tracking ID 104: slot 0 (explicit slot 0 assigned). This is the 2nd
        #                  slot in the packet. A slot 1 has already existed.
        list_104 = [(780, 373), (780, 372), (780, 372), (780, 372), (780, 373),
                    (780, 373), (781, 373)]
        for i, xy_pair in enumerate(list_95):
            self.assertEqual(Point(*xy_pair), tid_data_dict[95].points[i])
        for i, xy_pair in enumerate(list_104):
            self.assertEqual(Point(*xy_pair), tid_data_dict[104].points[i])

    def test_get_points_for_every_tracking_id3(self):
        filename = 'drumroll_3.dat'
        gesture_filename = self._get_filepath(filename)
        mtb_packets = get_mtb_packets(gesture_filename)
        tid_data_dict = mtb_packets.get_points_for_every_tracking_id()
        # Check points in one tracking ID: 582
        # Tracking ID 582: slot 9. This is the 2nd slot in the packet.
        #                  A slot 8 has already existed.
        list_582 = [(682, 173), (667, 186), (664, 189), (664, 190), (664, 189),
                    (665, 189), (665, 189), (667, 188), (675, 185), (683, 181),
                    (693, 172), (469, 381), (471, 395), (471, 396)]
        for i, xy_pair in enumerate(list_582):
            self.assertEqual(Point(*xy_pair), tid_data_dict[582].points[i])

    def test_convert_to_evemu_format(self):
        evemu_filename = self._get_filepath('one_finger_swipe.evemu.dat')
        mtplot_filename = self._get_filepath('one_finger_swipe.dat')
        packets = mtb.MtbParser().parse_file(mtplot_filename)
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

    def test_get_largest_gap_ratio(self):
        """Test get_largest_gap_ratio for one-finger and two-finger gestures."""
        # The following files come with noticeable large gaps.
        list_large_ratio = [
            'one_finger_tracking.left_to_right.slow_1.dat',
            'two_finger_gaps.vertical.dat',
            'two_finger_gaps.horizontal.dat',
            'resting_finger_2nd_finger_moving_segment_gaps.dat',
            'gap_new_finger_arriving_or_departing.dat',
            'one_stationary_finger_2nd_finger_moving_gaps.dat',
            'resting_finger_2nd_finger_moving_gaps.dat',
        ]
        gesture_slots = {
            'one_finger': [0,],
            'two_finger': [0, 1],
            'resting_finger': [1,],
            'gap_new_finger': [0,],
            'one_stationary_finger': [1,],
        }

        range_middle = self._get_range_middle(conf.no_gap_criteria)
        gap_data_dir = self._get_filepath('gaps')
        gap_data_filenames = glob.glob(os.path.join(gap_data_dir, '*.dat'))
        for filename in gap_data_filenames:
            mtb_packets = get_mtb_packets(filename)
            base_filename = os.path.basename(filename)

            # What slots to check are based on the gesture name.
            slots = []
            for gesture in gesture_slots:
                if base_filename.startswith(gesture):
                    slots = gesture_slots[gesture]
                    break

            for slot in slots:
                largest_gap_ratio = mtb_packets.get_largest_gap_ratio(slot)
                if base_filename in list_large_ratio:
                    self.assertTrue(largest_gap_ratio >= range_middle)
                else:
                    self.assertTrue(largest_gap_ratio < range_middle)

    def test_get_largest_accumulated_level_jumps(self):
        """Test get_largest_accumulated_level_jumps."""
        dir_level_jumps = 'drag_edge_thumb'

        filenames = [
            # filenames with level jumps
            # ----------------------------------
            'drag_edge_thumb.horizontal.dat',
            'drag_edge_thumb.horizontal_2.dat',
            # test no points in some tracking ID
            'drag_edge_thumb.horizontal_3.no_points.dat',
            'drag_edge_thumb.vertical.dat',
            'drag_edge_thumb.vertical_2.dat',
            'drag_edge_thumb.diagonal.dat',
            # Change tracking IDs quickly.
            'drag_edge_thumb.horizontal_4.change_ids_quickly.dat',

            # filenames without level jumps
            # ----------------------------------
            'drag_edge_thumb.horizontal.curvy.dat',
            'drag_edge_thumb.horizontal_2.curvy.dat',
            'drag_edge_thumb.vertical.curvy.dat',
            'drag_edge_thumb.vertical_2.curvy.dat',
            # Rather small level jumps
            'drag_edge_thumb.horizontal_5.small_level_jumps.curvy.dat',
        ]

        largest_level_jumps = {
            # Large jumps
            'drag_edge_thumb.horizontal.dat': {AXIS.X: 0, AXIS.Y: 97},
            # Smaller jumps
            'drag_edge_thumb.horizontal_2.dat': {AXIS.X: 0, AXIS.Y: 24},
            # test no points in some tracking ID
            'drag_edge_thumb.horizontal_3.no_points.dat':
                    {AXIS.X: 97, AXIS.Y: 88},
            # Change tracking IDs quickly.
            'drag_edge_thumb.horizontal_4.change_ids_quickly.dat':
                    {AXIS.X: 0, AXIS.Y: 14},
            # Large jumps
            'drag_edge_thumb.vertical.dat': {AXIS.X: 54, AXIS.Y: 0},
            # The first slot 0 comes with smaller jumps only.
            'drag_edge_thumb.vertical_2.dat': {AXIS.X: 20, AXIS.Y: 0},
            # Large jumps
            'drag_edge_thumb.diagonal.dat': {AXIS.X: 84, AXIS.Y: 58},
        }

        target_slot = 0
        for filename in filenames:
            filepath = self._get_filepath(filename, gesture_dir=dir_level_jumps)
            packets = get_mtb_packets(filepath)
            displacements = packets.get_displacements_for_slots(target_slot)

            # There are no level jumps in a curvy line.
            file_with_level_jump = 'curvy' not in filename

            # Check the first slot only
            tids = displacements.keys()
            tids.sort()
            tid = tids[0]
            # Check both axis X and axis Y
            for axis in AXIS.LIST:
                disp = displacements[tid][axis]
                jump = packets.get_largest_accumulated_level_jumps(disp)
                # Verify that there are no jumps in curvy files, and
                #        that there are jumps in the other files.
                expected_jump = (0 if not file_with_level_jump
                                   else largest_level_jumps[filename][axis])
                self.assertTrue(jump == expected_jump)

    def _test_get_report_rate(self, filename, value):
        """Test get_report_rate."""
        gesture_filename = self._get_filepath(filename)
        mtb_packets = get_mtb_packets(gesture_filename)
        report_rate = round(mtb_packets.get_report_rate(), 2)
        self.assertAlmostEqual(report_rate, value)

    def test_get_report_rate(self):
        """Test get_report_rate."""
        filename = '2f_scroll_diagonal.dat'
        self._test_get_report_rate('2f_scroll_diagonal.dat', 40.31)

        filename = 'one_finger_with_slot_0.dat'
        self._test_get_report_rate(filename, 148.65)

        filename = 'two_close_fingers_merging_changed_ids_gaps.dat'
        self._test_get_report_rate(filename, 53.12)


if __name__ == '__main__':
  unittest.main()
