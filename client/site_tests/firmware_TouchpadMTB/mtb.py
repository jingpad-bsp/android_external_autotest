# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides MTB parser and related packet methods."""

import logging
import math
import os
import re
import sys

sys.path.append('/usr/local/autotest/bin/input')
from linux_input import *

# Include some constants
execfile('firmware_constants.py', globals())


def make_pretty_packet(packet):
    """Convert the event list in a packet to a pretty format."""
    pretty_packet = []
    for event in packet:
        pretty_event = []
        pretty_event.append('Event:')
        pretty_event.append('time %.6f,' % event[EV_TIME])
        if event.get(SYN_REPORT):
            pretty_event.append('-------------- SYN_REPORT ------------\n')
        else:
            ev_type = event[EV_TYPE]
            pretty_event.append('type %d (%s),' % (ev_type, EV_TYPES[ev_type]))
            ev_code = event[EV_CODE]
            pretty_event.append('code %d (%s),' %
                                 (ev_code, EV_STRINGS[ev_type][ev_code]))
            pretty_event.append('value %d' % event[EV_VALUE])
        pretty_packet.append(' '.join(pretty_event))
    return '\n'.join(pretty_packet)


class MTB:
    """An MTB class providing MTB format related utility methods."""

    def __init__(self, packets):
        self.packets = packets

    def _is_ABS_MT_TRACKING_ID(self, event):
        """Is this event ABS_MT_TRACKING_ID?"""
        return (not event.get(SYN_REPORT) and
                event[EV_TYPE] == EV_ABS and
                event[EV_CODE] == ABS_MT_TRACKING_ID)

    def _is_new_contact(self, event):
        """Is this packet generating new contact (Tracking ID)?"""
        return self._is_ABS_MT_TRACKING_ID(event) and event[EV_VALUE] != -1

    def _is_finger_leaving(self, event):
        """Is the finger is leaving in this packet?"""
        return self._is_ABS_MT_TRACKING_ID(event) and event[EV_VALUE] == -1

    def _is_ABS_MT_SLOT(self, event):
        """Is this packet ABS_MT_SLOT?"""
        return (not event.get(SYN_REPORT) and
                event[EV_TYPE] == EV_ABS and
                event[EV_CODE] == ABS_MT_SLOT)

    def _is_ABS_MT_POSITION_X(self, event):
        """Is this packet ABS_MT_POSITION_X?"""
        return (not event.get(SYN_REPORT) and
                event[EV_TYPE] == EV_ABS and
                event[EV_CODE] == ABS_MT_POSITION_X)

    def _is_ABS_MT_POSITION_Y(self, event):
        """Is this packet ABS_MT_POSITION_Y?"""
        return (not event.get(SYN_REPORT) and
                event[EV_TYPE] == EV_ABS and
                event[EV_CODE] == ABS_MT_POSITION_Y)

    def _calc_movement_for_axis(self, x, prev_x):
        """Calculate the distance moved in an axis."""
        return abs(x - prev_x) if prev_x is not None else 0

    def _calc_distance(self, (x0, y0), (x1, y1)):
        """Calculate the distance between two points."""
        dist_x = x1 - x0
        dist_y = y1 - y0
        return math.sqrt(dist_x * dist_x + dist_y * dist_y)

    def _init_dict(self, keys, value):
        """Initialize a dictionary over the keys with the same given value.

        Note: The following command does not always work:
                    dict.fromkeys(keys, value)
              It works when value is a simple type, e.g., an integer.
              However, if value is [] or {}, it does not work correctly.
              The reason is that if the value is [] or {}, all the keys would
              point to the same list or dictionary, which is not expected
              in most cases.
        """
        return dict([(key, value) for key in keys])

    def get_number_contacts(self):
        """Get the number of contacts (Tracking IDs)."""
        num_contacts = 0
        for packet in self.packets:
            for event in packet:
                if self._is_new_contact(event):
                    num_contacts += 1
        return num_contacts

    def get_x_y(self, target_slot):
        """Extract x and y positions in the target slot."""
        slot = 0
        list_x = []
        list_y = []
        prev_x = prev_y = None
        for packet in self.packets:
            found_flag = False
            for event in packet:
                if self._is_ABS_MT_SLOT(event):
                    slot = event[EV_VALUE]
                elif self._is_ABS_MT_POSITION_X(event) and slot == target_slot:
                    prev_x = event[EV_VALUE]
                    found_flag = True
                elif self._is_ABS_MT_POSITION_Y(event) and slot == target_slot:
                    prev_y = event[EV_VALUE]
                    found_flag = True
            # If either x or y positions are reported in the current packet,
            # append the x and y to the list.
            # This handles the condition that only x or y is reported.
            # This also handles the initial condition that no previous x or y
            # is reported yet.
            if found_flag and prev_x and prev_y:
                list_x.append(prev_x)
                list_y.append(prev_y)
        return (list_x, list_y)

    def get_x_y_multiple_slots(self, target_slots):
        """Extract points in multiple slots.

        Only the packets with all specified slots are extracted.
        This is useful to collect packets for pinch to zoom.
        """
        # Initialize slot_exists dictionary to False
        slot_exists = dict.fromkeys(target_slots, False)

        # Set the initial slot number to 0 because evdev is a state machine,
        # and may not present slot 0.
        slot = 0
        # Initialze the following dict to []
        # Don't use "dict.fromkeys(target_slots, [])"
        list_x = self._init_dict(target_slots, [])
        list_y = self._init_dict(target_slots, [])
        x = self._init_dict(target_slots, None)
        y = self._init_dict(target_slots, None)
        for packet in self.packets:
            for event in packet:
                if self._is_ABS_MT_SLOT(event):
                    slot = event[EV_VALUE]
                if slot not in target_slots:
                    continue

                if self._is_ABS_MT_TRACKING_ID(event):
                    if self._is_new_contact(event):
                        slot_exists[slot] = True
                    elif self._is_finger_leaving(event):
                        slot_exists[slot] = False
                elif self._is_ABS_MT_POSITION_X(event):
                    x[slot] = event[EV_VALUE]
                elif self._is_ABS_MT_POSITION_Y(event):
                    y[slot] = event[EV_VALUE]

            # Note:
            # - All slot_exists must be True to append x, y positions for the
            #   slots.
            # - All x and y values for all slots must have been reported once.
            #   (This handles the initial condition that no previous x or y
            #    is reported yet.)
            # - If either x or y positions are reported in the current packet,
            #   append x and y to the list of that slot.
            #   (This handles the condition that only x or y is reported.)
            # - Even in the case that neither x nor y is reported in current
            #   packet, cmt driver constructs and passes hwstate to gestures.
            if (all(slot_exists.values()) and all(x.values()) and
                all(y.values())):
                for slot in target_slots:
                    list_x[slot].append(x[slot])
                    list_y[slot].append(y[slot])

        return (list_x, list_y)

    def get_points_multiple_slots(self, target_slots):
        """Get the points in multiple slots."""
        list_x, list_y = self.get_x_y_multiple_slots(target_slots)
        points_list = [zip(list_x[slot], list_y[slot]) for slot in target_slots]
        points_dict = dict(zip(target_slots, points_list))
        return points_dict

    def get_relative_motion(self, target_slots):
        """Get the relative motion of the two target slots."""
        # The slots in target_slots could be (0, 1), (1, 2) or other
        # possibilities.
        slot_a, slot_b = target_slots
        points_dict = self.get_points_multiple_slots(target_slots)
        points_slot_a = points_dict[slot_a]
        points_slot_b = points_dict[slot_b]

        # if only 0 or 1 point observed, the relative motion is 0.
        if len(points_slot_a) <= 1 or len(points_slot_b) <= 1:
            return 0

        distance_begin = self._calc_distance(points_slot_a[0], points_slot_b[0])
        distance_end = self._calc_distance(points_slot_a[-1], points_slot_b[-1])
        relative_motion = distance_end - distance_begin
        return relative_motion

    def get_points(self, target_slot):
        """Get the points in the target slot."""
        list_x, list_y = self.get_x_y(target_slot)
        return zip(list_x, list_y)

    def get_distances(self, target_slot):
        """Get the distances of neighbor points in the target slot."""
        points = self.get_points(target_slot)
        distances = []
        for index in range(len(points) - 1):
            distance = self._calc_distance(points[index], points[index + 1])
            distances.append(distance)
        return distances

    def get_distances_with_first_point(self, target_slot):
        """Get distances of the points in the target_slot with first point."""
        points = self.get_points(target_slot)
        point0 = points[0]
        distances = [self._calc_distance(point, point0) for point in points]
        return distances

    def get_range(self):
        """Get the min and max values of (x, y) positions."""
        min_x = min_y = float('infinity')
        max_x = max_y = float('-infinity')
        for packet in self.packets:
            for event in packet:
                if self._is_ABS_MT_POSITION_X(event):
                    x = event[EV_VALUE]
                    min_x = min(min_x, x)
                    max_x = max(max_x, x)
                elif self._is_ABS_MT_POSITION_Y(event):
                    y = event[EV_VALUE]
                    min_y = min(min_y, y)
                    max_y = max(max_y, y)
        return (min_x, max_x, min_y, max_y)

    def get_total_motion(self, target_slot):
        """Get the total motion in the target slot."""
        prev_x = prev_y = None
        accu_x = accu_y = 0
        slot = None
        for packet in self.packets:
            for event in packet:
                if self._is_ABS_MT_SLOT(event):
                    slot = event[EV_VALUE]
                elif self._is_ABS_MT_POSITION_X(event) and slot == target_slot:
                    x = event[EV_VALUE]
                    accu_x += self._calc_movement_for_axis(x, prev_x)
                    prev_x = x
                elif self._is_ABS_MT_POSITION_Y(event) and slot == target_slot:
                    y = event[EV_VALUE]
                    accu_y += self._calc_movement_for_axis(y, prev_y)
                    prev_y = y
        return (accu_x, accu_y)

    def get_largest_distance(self, target_slot):
        """Get the largest distance of point to the first point."""
        distances = self.get_distances_with_first_point(target_slot)
        return max(distances)

    def get_largest_gap_ratio(self, target_slot):
        """Get the largest gap ratio in the target slot."""
        gaps = self.get_distances(target_slot)
        gap_ratios = []
        for index in range(1, len(gaps) - 1):
            prev_gap = max(gaps[index - 1], 1)
            curr_gap = gaps[index]
            next_gap = max(gaps[index + 1], 1)
            gap_ratios.append(2.0 * curr_gap / (prev_gap + next_gap))
        largest_gap_ratio = max(gap_ratios) if gap_ratios else 0
        return largest_gap_ratio

    def get_displacement(self, target_slot):
        """Get the displacement in the target slot."""
        displace = [map(lambda p0, p1: p1 - p0, axis[:len(axis) - 1], axis[1:])
                    for axis in self.get_x_y(target_slot)]
        displacement_dict = dict(zip((X, Y), displace))
        return displacement_dict

    def get_reversed_motions(self, target_slot, direction):
        """Get the total reversed motions in the specified direction
           in the target slot.

        If direction is HORIZONTAL, consider only x axis.
        If direction is VERTICAL, consider only y axis.
        If direction is DIAGONAL, consider both x and y axes.

        Assume that a list of displacement in some axis looks like
            [10, 12, 8, -9, -2, 6, 8, 11, 12, 5, 2]

        The number of positive displacements, which is 9, is greater than
        the number of negative displacements, which is 2. In this case
        (-9) + (-2) = -11 is the total reversed motion in this list.

        Should the number of positive items be equal to the number of negative
        items, we assume that the one with smaller sum is the reversed motion.
        Take this list [10, 22, -9, -2, -3, 10] for example. The numbers of
        items for both positive/negative displacements are the same. However,
        the sum of negative values is smaller. Hence, the reversed motion is
        the sum of negative values.
        """
        check_axes = {HORIZONTAL: (X,), VERTICAL: (Y,), DIAGONAL: (X, Y)}
        displacement_dict = self.get_displacement(target_slot)

        reversed_motions = {}
        func_positive = lambda n: n > 0
        func_negative = lambda n: n < 0
        for axis in check_axes[direction]:
            displacement = displacement_dict[axis]
            list_positive = filter(func_positive, displacement)
            list_negative = filter(func_negative, displacement)
            num_positive = len(list_positive)
            num_negative = len(list_negative)
            sum_positive = sum(list_positive)
            sum_negative = sum(list_negative)
            if num_positive > num_negative:
                reversed_motions[axis] = sum_negative
            elif num_positive < num_negative:
                reversed_motions[axis] = sum_positive
            # Handle the very rare case below when num_positive == num_negative
            elif sum_positive >= sum_negative:
                reversed_motions[axis] = sum_negative
            elif sum_positive < sum_negative:
                reversed_motions[axis] = sum_positive
        return reversed_motions

    def get_num_packets(self, target_slot):
        """Get the number of packets in the target slot."""
        list_x, list_y = self.get_x_y(target_slot)
        return len(list_x)


class MTBParser:
    """Touchpad MTB event Parser."""

    def __init__(self):
        self._get_event_re_patt()

    def _get_event_re_patt(self):
        """Construct the regular expression search pattern of MTB events.

        An ordinary event looks like
          Event: time 133082.748019, type 3 (EV_ABS), code 0 (ABS_X), value 316
        A SYN_REPORT event looks like
          Event: time 10788.289613, -------------- SYN_REPORT ------------
        """
        # Get the pattern of an ordinary event
        event_patt_time = 'Event:\s*time\s*(\d+\.\d+)'
        event_patt_type = 'type\s*(\d+)\s*\(\w+\)'
        event_patt_code = 'code\s*(\d+)\s*\(\w+\)'
        event_patt_value = 'value\s*(-?\d+)'
        event_sep = ',\s*'
        event_patt = event_sep.join([event_patt_time,
                                     event_patt_type,
                                     event_patt_code,
                                     event_patt_value])
        self.event_re_patt = re.compile(event_patt, re.I)

        # Get the pattern of the SYN_REPORT event
        event_patt_type_SYN_REPORT = '-+\s*SYN_REPORT\s-+'
        event_patt_SYN_REPORT = event_sep.join([event_patt_time,
                                                event_patt_type_SYN_REPORT])
        self.event_re_patt_SYN_REPORT = re.compile(event_patt_SYN_REPORT, re.I)

    def _get_event_dict_ordinary(self, line):
        """Construct the event dictionary for an ordinary event."""
        result = self.event_re_patt.search(line)
        ev_dict = {}
        if result is not None:
            ev_dict[EV_TIME] = float(result.group(1))
            ev_dict[EV_TYPE] = int(result.group(2))
            ev_dict[EV_CODE] = int(result.group(3))
            ev_dict[EV_VALUE] = int(result.group(4))
        return ev_dict

    def _get_event_dict_SYN_REPORT(self, line):
        """Construct the event dictionary for a SYN_REPORT event."""
        result = self.event_re_patt_SYN_REPORT.search(line)
        ev_dict = {}
        if result is not None:
            ev_dict[EV_TIME] = float(result.group(1))
            ev_dict[SYN_REPORT] = True
        return ev_dict

    def _get_event_dict(self, line):
        """Construct the event dictionary."""
        EVENT_FUNC_LIST = [self._get_event_dict_ordinary,
                           self._get_event_dict_SYN_REPORT]
        for get_event_func in EVENT_FUNC_LIST:
            ev_dict = get_event_func(line)
            if ev_dict:
                return ev_dict
        return False

    def _is_SYN_REPORT(self, ev_dict):
        """Determine if this event is SYN_REPORT."""
        return ev_dict.get(SYN_REPORT, False)

    def parse(self, raw_event):
        """Parse the raw event string into a list of event dictionary."""
        ev_list = []
        packets = []
        start_flag = False
        for line in raw_event:
            ev_dict = self._get_event_dict(line)
            if ev_dict:
                start_flag = True
                ev_list.append(ev_dict)
                if self._is_SYN_REPORT(ev_dict):
                    packets.append(ev_list)
                    ev_list = []
            elif start_flag:
                logging.warn('  Warn: format problem in event:\n  %s' % line)
        return packets

    def parse_file(self, file_name):
        """Parse raw device events in the given file name."""
        packets = None
        if os.path.isfile(file_name):
            with open(file_name) as f:
                packets = self.parse(f)
        return packets


if __name__ == '__main__':
    # Read a device file, and convert it to pretty packet format.
    if len(sys.argv) != 2 or not os.path.exists(sys.argv[1]):
        print 'Usage: %s device_file' % sys.argv[0]
        exit(1)

    with open(sys.argv[1]) as event_file:
        packets = MTBParser().parse(event_file)
    for packet in packets:
        print make_pretty_packet(packet)
