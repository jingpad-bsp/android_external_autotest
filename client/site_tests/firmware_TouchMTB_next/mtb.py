# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides MTB parser and related packet methods."""

import copy
import logging
import math
import os
import re
import sys

from firmware_constants import AXIS, GV, MTB, VAL
sys.path.append('../../bin/input')
from linux_input import *


def make_pretty_packet(packet):
    """Convert the event list in a packet to a pretty format."""
    pretty_packet = []
    for event in packet:
        pretty_event = []
        pretty_event.append('Event:')
        pretty_event.append('time %.6f,' % event[MTB.EV_TIME])
        if event.get(MTB.SYN_REPORT):
            pretty_event.append('-------------- SYN_REPORT ------------\n')
        else:
            ev_type = event[MTB.EV_TYPE]
            pretty_event.append('type %d (%s),' % (ev_type, EV_TYPES[ev_type]))
            ev_code = event[MTB.EV_CODE]
            pretty_event.append('code %d (%s),' %
                                 (ev_code, EV_STRINGS[ev_type][ev_code]))
            pretty_event.append('value %d' % event[MTB.EV_VALUE])
        pretty_packet.append(' '.join(pretty_event))
    return '\n'.join(pretty_packet)


def convert_to_evemu_format(packets):
    """Convert the text event format to the evemu format."""
    evemu_output = []
    evemu_format = 'E: %.6f %04x %04x %d'
    evemu_format_syn_report = 'E: %.6f 0000 0000 0'
    for packet in packets:
        for event in packet:
            if event.get(MTB.SYN_REPORT):
                evemu_event = evemu_format_syn_report % event[MTB.EV_TIME]
            else:
                evemu_event = evemu_format % (event[MTB.EV_TIME],
                                              event[MTB.EV_TYPE],
                                              event[MTB.EV_CODE],
                                              event[MTB.EV_VALUE])
            evemu_output.append(evemu_event)
    return evemu_output


def convert_mtplot_file_to_evemu_file(mtplot_filename, evemu_ext='.evemu',
                                      force=False):
    """Convert a mtplot event file to an evemu event file.

    Example:
       'one_finger_swipe.dat' is converted to 'one_finger_swipe.evemu.dat'
    """
    if not os.path.isfile(mtplot_filename):
        print 'Error: there is no such file: "%s".' % mtplot_filename
        return

    # Convert mtplot event format to evemu event format.
    mtplot_packets = MtbParser().parse_file(mtplot_filename)
    evemu_packets = convert_to_evemu_format(mtplot_packets)

    # Create the evemu filename from the mtplot filename.
    mtplot_root, mtplot_ext = os.path.splitext(mtplot_filename)
    evemu_filename = mtplot_root + evemu_ext + mtplot_ext

    # Make sure that the file to be created does not exist yet unless force flag
    # is set to be True.
    if os.path.isfile(evemu_filename) and not force:
        print 'Warning: the "%s" already exists.' % evemu_filename
        return

    # Write the converted evemu events to the evemu file.
    with open(evemu_filename, 'w') as evemu_f:
        evemu_f.write('\n'.join(evemu_packets))


class MtbEvemu:
    """A simplified class provides MTB utilities for evemu event format."""
    def __init__(self):
        self.mtb = Mtb()
        self.num_tracking_ids = 0

    def _convert_event(self, event):
        (tv_sec, tv_usec, ev_type, ev_code, ev_value) = event
        ev_dict = {MTB.EV_TIME: tv_sec + 0.000001 * tv_usec,
                   MTB.EV_TYPE: ev_type,
                   MTB.EV_CODE: ev_code,
                   MTB.EV_VALUE: ev_value}
        return ev_dict

    def all_fingers_leaving(self):
        """Is there no finger on the touch device?"""
        return self.num_tracking_ids <= 0

    def process_event(self, event):
        """Process the event and count existing fingers."""
        converted_event = self._convert_event(event)
        if self.mtb._is_new_contact(converted_event):
            self.num_tracking_ids += 1
        elif self.mtb._is_finger_leaving(converted_event):
            self.num_tracking_ids -= 1


class Mtb:
    """An MTB class providing MTB format related utility methods."""
    LEN_MOVING_AVERAGE = 2
    LEVEL_JUMP_RATIO = 3
    LEVEL_JUMP_MAXIUM_ALLOWED = 10
    LEN_DISCARD = 5

    def __init__(self, packets=None):
        self.packets = packets
        self._define_check_event_func_list()

    def _define_check_event_func_list(self):
        """Define event function lists for various event cycles below."""
        self.check_event_func_list = {}
        self.MAX_FINGERS = 5
        # One-finger touching the device should generate the following events:
        #     BTN_TOUCH, and BTN_TOOL_FINGER: 0 -> 1 -> 0
        self.check_event_func_list[1] = [self._is_BTN_TOUCH,
                                         self._is_BTN_TOOL_FINGER]

        # Two-finger touching the device should generate the following events:
        #     BTN_TOUCH, and BTN_TOOL_DOUBLETAP: 0 -> 1 -> 0
        self.check_event_func_list[2] = [self._is_BTN_TOUCH,
                                         self._is_BTN_TOOL_DOUBLETAP]

        # Three-finger touching the device should generate the following events:
        #     BTN_TOUCH, and BTN_TOOL_TRIPLETAP: 0 -> 1 -> 0
        self.check_event_func_list[3] = [self._is_BTN_TOUCH,
                                         self._is_BTN_TOOL_TRIPLETAP]

        # Four-finger touching the device should generate the following events:
        #     BTN_TOUCH, and BTN_TOOL_QUADTAP: 0 -> 1 -> 0
        self.check_event_func_list[4] = [self._is_BTN_TOUCH,
                                         self._is_BTN_TOOL_QUADTAP]

        # Five-finger touching the device should generate the following events:
        #     BTN_TOUCH, and BTN_TOOL_QUINTTAP: 0 -> 1 -> 0
        self.check_event_func_list[5] = [self._is_BTN_TOUCH,
                                         self._is_BTN_TOOL_QUINTTAP]

        # Physical click should generate the following events:
        #     BTN_LEFT: 0 -> 1 -> 0
        self.check_event_func_click = [self._is_BTN_LEFT,]


    def _is_ABS_MT_TRACKING_ID(self, event):
        """Is this event ABS_MT_TRACKING_ID?"""
        return (not event.get(MTB.SYN_REPORT) and
                event[MTB.EV_TYPE] == EV_ABS and
                event[MTB.EV_CODE] == ABS_MT_TRACKING_ID)

    def _is_new_contact(self, event):
        """Is this packet generating new contact (Tracking ID)?"""
        return self._is_ABS_MT_TRACKING_ID(event) and event[MTB.EV_VALUE] != -1

    def _is_finger_leaving(self, event):
        """Is the finger is leaving in this packet?"""
        return self._is_ABS_MT_TRACKING_ID(event) and event[MTB.EV_VALUE] == -1

    def _is_ABS_MT_SLOT(self, event):
        """Is this packet ABS_MT_SLOT?"""
        return (not event.get(MTB.SYN_REPORT) and
                event[MTB.EV_TYPE] == EV_ABS and
                event[MTB.EV_CODE] == ABS_MT_SLOT)

    def _is_ABS_MT_POSITION_X(self, event):
        """Is this packet ABS_MT_POSITION_X?"""
        return (not event.get(MTB.SYN_REPORT) and
                event[MTB.EV_TYPE] == EV_ABS and
                event[MTB.EV_CODE] == ABS_MT_POSITION_X)

    def _is_ABS_MT_POSITION_Y(self, event):
        """Is this packet ABS_MT_POSITION_Y?"""
        return (not event.get(MTB.SYN_REPORT) and
                event[MTB.EV_TYPE] == EV_ABS and
                event[MTB.EV_CODE] == ABS_MT_POSITION_Y)

    def _is_EV_KEY(self, event):
        """Is this an EV_KEY event?"""
        return (not event.get(MTB.SYN_REPORT) and event[MTB.EV_TYPE] == EV_KEY)

    def _is_BTN_LEFT(self, event):
        """Is this event BTN_LEFT?"""
        return (self._is_EV_KEY(event) and event[MTB.EV_CODE] == BTN_LEFT)

    def _is_BTN_TOOL_FINGER(self, event):
        """Is this event BTN_TOOL_FINGER?"""
        return (self._is_EV_KEY(event) and
                event[MTB.EV_CODE] == BTN_TOOL_FINGER)

    def _is_BTN_TOOL_DOUBLETAP(self, event):
        """Is this event BTN_TOOL_DOUBLETAP?"""
        return (self._is_EV_KEY(event) and
                event[MTB.EV_CODE] == BTN_TOOL_DOUBLETAP)

    def _is_BTN_TOOL_TRIPLETAP(self, event):
        """Is this event BTN_TOOL_TRIPLETAP?"""
        return (self._is_EV_KEY(event) and
                event[MTB.EV_CODE] == BTN_TOOL_TRIPLETAP)

    def _is_BTN_TOOL_QUADTAP(self, event):
        """Is this event BTN_TOOL_QUADTAP?"""
        return (self._is_EV_KEY(event) and
                event[MTB.EV_CODE] == BTN_TOOL_QUADTAP)

    def _is_BTN_TOOL_QUINTTAP(self, event):
        """Is this event BTN_TOOL_QUINTTAP?"""
        return (self._is_EV_KEY(event) and
                event[MTB.EV_CODE] == BTN_TOOL_QUINTTAP)

    def _is_BTN_TOUCH(self, event):
        """Is this event BTN_TOUCH?"""
        return (self._is_EV_KEY(event) and
                event[MTB.EV_CODE] == BTN_TOUCH)

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
        return dict([(key, copy.deepcopy(value)) for key in keys])

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
        # The default slot is slot 0 if no slot number is assigned.
        # The rationale is that evdev is a state machine. It only reports
        # the change. Slot 0 would not be reported by evdev if last time
        # the last finger left the touch device was at slot 0.
        slot = 0

        # Should not write "list_x = list_y = []" below.
        # They would end up with pointing to the same list.
        list_x = []
        list_y = []
        prev_x = prev_y = None
        target_slot_live = False
        initial_default_slot_0 = True
        for packet in self.packets:
            if (slot == target_slot and slot == 0 and not target_slot_live and
                initial_default_slot_0):
                target_slot_live = True
                initial_default_slot_0 = False
            for event in packet:
                if self._is_ABS_MT_SLOT(event):
                    slot = event[MTB.EV_VALUE]
                    if slot == target_slot and not target_slot_live:
                        target_slot_live = True
                if slot != target_slot:
                    continue

                # Update x value if available.
                if self._is_ABS_MT_POSITION_X(event):
                    prev_x = event[MTB.EV_VALUE]
                # Update y value if available.
                elif self._is_ABS_MT_POSITION_Y(event):
                    prev_y = event[MTB.EV_VALUE]
                # Check if the finger at the target_slot is leaving.
                elif self._is_finger_leaving(event):
                    target_slot_live = False

            # If target_slot is alive, and both x and y have
            # been assigned values, append the x and y to the list no matter
            # whether x or y position is reported in the current packet.
            # This also handles the initial condition that no previous x or y
            # is reported yet.
            if target_slot_live and prev_x and prev_y:
                list_x.append(prev_x)
                list_y.append(prev_y)
        return (list_x, list_y)

    def get_points_for_every_tracking_id(self):
        """Extract points in every tracking id.

        This method is applicable when fingers are contacting and leaving
        the touch device continuously. The same slot number, e.g., slot 0 or
        slot 1, may be used for multiple times.
        """
        # The default slot is slot 0 if no slot number is assigned.
        slot = 0

        # points is a dictionary of lists, where each list holds all of
        # the points in a tracking id.
        points = {}
        tracking_ids_all = []
        tracking_ids_live = []
        slot_to_tracking_id = {}
        x = {}
        y = {}
        for packet in self.packets:
            for event in packet:
                if self._is_ABS_MT_SLOT(event):
                    slot = event[MTB.EV_VALUE]

                # Find a new tracking ID
                if self._is_new_contact(event):
                    tracking_id = event[MTB.EV_VALUE]
                    tracking_ids_all.append(tracking_id)
                    tracking_ids_live.append(tracking_id)
                    points[tracking_id] = {}
                    points[tracking_id][MTB.POINTS] = []
                    points[tracking_id][MTB.SLOT] = slot
                    slot_to_tracking_id[slot] = tracking_id
                    x[tracking_id] = None
                    y[tracking_id] = None

                # A tracking ID is leaving.
                elif self._is_finger_leaving(event):
                    leaving_tracking_id = slot_to_tracking_id[slot]
                    tracking_ids_live.remove(leaving_tracking_id)
                    del slot_to_tracking_id[slot]

                # Update x value if available.
                elif self._is_ABS_MT_POSITION_X(event):
                    x[slot_to_tracking_id[slot]] = event[MTB.EV_VALUE]

                # Update y value if available.
                elif self._is_ABS_MT_POSITION_Y(event):
                    y[slot_to_tracking_id[slot]] = event[MTB.EV_VALUE]

            for tracking_id in tracking_ids_live:
                if x[tracking_id] and y[tracking_id]:
                    curr_point = (x[tracking_id], y[tracking_id])
                    points[tracking_id][MTB.POINTS].append(curr_point)

        return points

    def _calc_farthest_distance(self, points):
        """Calculate the farthest distance of points."""
        # TODO(josephsih): track state across different tracking IDs.
        # The evdev driver only reports the delta of a slot state. It may only
        # reports x positions if y positions are exactly the same as those
        # generated by previous finger with the same slot ID. In this special
        # case, the points would be an empty list. If we could track the
        # states including x, y positions and z pressure, we could fill in
        # those information into the points. The empty points cases may happen
        # when performing drumroll gestures.
        if not points:
            return 0
        return max([self._calc_distance(point, points[0]) for point in points])

    def get_max_distance_of_all_tracking_ids(self):
        """Get the max moving distance of all tracking IDs."""
        points = self.get_points_for_every_tracking_id()
        max_distance = float('-infinity')
        for tracking_id in sorted(points.keys()):
            slot_points = points[tracking_id][MTB.POINTS]
            distance = self._calc_farthest_distance(slot_points)
            max_distance = max(max_distance, distance)
        return max_distance

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
        # Initialize the following dict to []
        # Don't use "dict.fromkeys(target_slots, [])"
        list_x = self._init_dict(target_slots, [])
        list_y = self._init_dict(target_slots, [])
        x = self._init_dict(target_slots, None)
        y = self._init_dict(target_slots, None)
        for packet in self.packets:
            for event in packet:
                if self._is_ABS_MT_SLOT(event):
                    slot = event[MTB.EV_VALUE]
                if slot not in target_slots:
                    continue

                if self._is_ABS_MT_TRACKING_ID(event):
                    if self._is_new_contact(event):
                        slot_exists[slot] = True
                    elif self._is_finger_leaving(event):
                        slot_exists[slot] = False
                elif self._is_ABS_MT_POSITION_X(event):
                    x[slot] = event[MTB.EV_VALUE]
                elif self._is_ABS_MT_POSITION_Y(event):
                    y[slot] = event[MTB.EV_VALUE]

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
                for s in target_slots:
                    list_x[s].append(x[s])
                    list_y[s].append(y[s])

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
        if not points:
            return [0,]
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
                    x = event[MTB.EV_VALUE]
                    min_x = min(min_x, x)
                    max_x = max(max_x, x)
                elif self._is_ABS_MT_POSITION_Y(event):
                    y = event[MTB.EV_VALUE]
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
                    slot = event[MTB.EV_VALUE]
                elif self._is_ABS_MT_POSITION_X(event) and slot == target_slot:
                    x = event[MTB.EV_VALUE]
                    accu_x += self._calc_movement_for_axis(x, prev_x)
                    prev_x = x
                elif self._is_ABS_MT_POSITION_Y(event) and slot == target_slot:
                    y = event[MTB.EV_VALUE]
                    accu_y += self._calc_movement_for_axis(y, prev_y)
                    prev_y = y
        return (accu_x, accu_y)

    def get_largest_distance(self, target_slot):
        """Get the largest distance of point to the first point."""
        distances = self.get_distances_with_first_point(target_slot)
        return max(distances)

    def get_largest_gap_ratio(self, target_slot):
        """Get the largest gap ratio in the target slot.

        gap_ratio_with_prev = curr_gap / prev_gap
        gap_ratio_with_next = curr_gap / next_gap

        This function tries to find the largest gap_ratio_with_prev
        with the restriction that gap_ratio_with_next is larger than
        RATIO_THRESHOLD_CURR_GAP_TO_NEXT_GAP.

        The ratio threshold is used to prevent the gaps detected in a swipe.
        Note that in a swipe, the gaps tends to become larger and larger.
        """
        RATIO_THRESHOLD_CURR_GAP_TO_NEXT_GAP = 1.2
        GAP_LOWER_BOUND = 10

        gaps = self.get_distances(target_slot)
        gap_ratios = []
        largest_gap_ratio = float('-infinity')
        for index in range(1, len(gaps) - 1):
            prev_gap = max(gaps[index - 1], 1)
            curr_gap = gaps[index]
            next_gap = max(gaps[index + 1], 1)
            gap_ratio_with_prev = curr_gap / prev_gap
            gap_ratio_with_next = curr_gap / next_gap
            if (curr_gap >= GAP_LOWER_BOUND and
                gap_ratio_with_prev > largest_gap_ratio and
                gap_ratio_with_next > RATIO_THRESHOLD_CURR_GAP_TO_NEXT_GAP):
                largest_gap_ratio = gap_ratio_with_prev

        return largest_gap_ratio

    def _is_large(self, numbers, index):
        """Is the number at the index a large number compared to the moving
        average of the previous LEN_MOVING_AVERAGE numbers? This is used to
        determine if a distance is a level jump."""
        if index < self.LEN_MOVING_AVERAGE + 1:
            return False
        moving_sum = sum(numbers[index - self.LEN_MOVING_AVERAGE : index])
        moving_average = float(moving_sum) / self.LEN_MOVING_AVERAGE
        cond1 = numbers[index] >= self.LEVEL_JUMP_RATIO * moving_average
        cond2 = numbers[index] >= self.LEVEL_JUMP_MAXIUM_ALLOWED
        return cond1 and cond2

    def _accumulate_level_jumps(self, level_jumps):
        """Accumulate level jumps."""
        if not level_jumps:
            return []

        is_positive = level_jumps[0] > 0
        tmp_sum = 0
        accumulated_level_jumps = []
        for jump in level_jumps:
            # If current sign is the same as previous ones, accumulate it.
            if (jump > 0) is is_positive:
                tmp_sum += jump
            # If current jump has changed its sign, reset the tmp_sum to
            # accumulate the level_jumps onwards.
            else:
                accumulated_level_jumps.append(tmp_sum)
                tmp_sum = jump
                is_positive = not is_positive

        if tmp_sum != 0:
            accumulated_level_jumps.append(tmp_sum)
        return accumulated_level_jumps

    def get_largest_accumulated_level_jumps(self, displacements):
        """Get the largest accumulated level jumps in displacements."""
        largest_accumulated_level_jumps = 0
        if len(displacements) < self.LEN_MOVING_AVERAGE + 1:
            return largest_accumulated_level_jumps

        # Truncate some elements at both ends of the list which are not stable.
        displacements = displacements[self.LEN_DISCARD: -self.LEN_DISCARD]
        distances = map(abs, displacements)

        # E.g., displacements= [5, 6, 5, 6, 20, 3, 5, 4, 6, 21, 4, ...]
        #       level_jumps = [20, 21, ...]
        level_jumps = [disp for i, disp in enumerate(displacements)
                       if self._is_large(distances, i)]

        # E.g., level_jumps= [20, 21, -18, -25, 22, 18, -19]
        #       accumulated_level_jumps = [41, -43, 40, -19]
        #       largest_accumulated_level_jumps = 43
        accumulated_level_jumps = self._accumulate_level_jumps(level_jumps)
        if accumulated_level_jumps:
            abs_accumulated_level_jumps = map(abs, accumulated_level_jumps)
            largest_accumulated_level_jumps = max(abs_accumulated_level_jumps)

        return largest_accumulated_level_jumps

    def get_displacement(self, target_slot):
        """Get the displacement in the target slot."""
        displace = [map(lambda p0, p1: p1 - p0, axis[:len(axis) - 1], axis[1:])
                    for axis in self.get_x_y(target_slot)]
        displacement_dict = dict(zip((AXIS.X, AXIS.Y), displace))
        return displacement_dict

    def calc_displacement(self, numbers):
        """Calculate the displacements in a list of numbers."""
        if len(numbers) <= 1:
            return []
        return [numbers[i + 1] - numbers[i] for i in range(len(numbers) - 1)]

    def get_displacements_for_slots(self, min_slot):
        """Get the displacements for slots >= min_slot."""
        points = self.get_points_for_every_tracking_id()
        slots_to_delete = []

        # Collect those tracking IDs with slots < min_slot and delete them.
        # Python does not allow to modify a dictionary while iterating over it.
        for tid in points:
            slot = points[tid][MTB.SLOT]
            tid_points = points[tid][MTB.POINTS]
            if (slot < min_slot) or (tid_points == []):
                slots_to_delete.append(tid)
        for tid in slots_to_delete:
            del points[tid]

        # Calculate the displacements of the coordinates in the tracking IDs.
        displacements = {}
        for tid in points:
            list_x, list_y = zip(*points[tid][MTB.POINTS])
            displacements[tid] = {}
            displacements[tid][MTB.SLOT] = points[tid][MTB.SLOT]
            displacements[tid][AXIS.X] = self.calc_displacement(list_x)
            displacements[tid][AXIS.Y] = self.calc_displacement(list_y)

        return displacements

    def _get_segments(self, src_list, segment_flag, ratio):
        """Get the segments based on segment_flag and ratio."""
        end_size = int(round(len(src_list) * ratio))
        if segment_flag == VAL.WHOLE:
            return src_list
        elif segment_flag == VAL.MIDDLE:
            return src_list[end_size: -end_size]
        elif segment_flag == VAL.BEGIN:
            return src_list[: end_size]
        elif segment_flag == VAL.END:
            return src_list[-end_size:]
        elif segment_flag == VAL.BOTH_ENDS:
            bgn_segment = src_list[: end_size]
            end_segment = src_list[-end_size:]
            return bgn_segment + end_segment
        else:
            return None

    def get_segments_x_and_y(self, ax, ay, segment_flag, ratio):
        """Get the segments for both x and y axes."""
        segment_x = self._get_segments(ax, segment_flag, ratio)
        segment_y = self._get_segments(ay, segment_flag, ratio)
        return (segment_x, segment_y)

    def get_reversed_motions(self, target_slot, direction,
                             segment_flag=VAL.WHOLE, ratio=None):
        """Get the total reversed motions in the specified direction
           in the target slot.

        Only the reversed motions specified by the segment_flag are taken.
        The segment_flag could be
          VAL.BEGIN: the begin segment
          VAL.MIDDLE : the middle segment
          VAL.END : the end segment
          VAL.BOTH_ENDS : the segments at both ends
          VAL.WHOLE: the whole line

        The ratio represents the ratio of the BEGIN or END segment to the whole
        segment.

        If direction is in HORIZONTAL_DIRECTIONS, consider only x axis.
        If direction is in VERTICAL_DIRECTIONS, consider only y axis.
        If direction is in DIAGONAL_DIRECTIONS, consider both x and y axes.

        Assume that the displacements in GV.LR (moving from left to right)
        in the X axis are:

            [10, 12, 8, -9, -2, 6, 8, 11, 12, 5, 2]

        Its total reversed motion = (-9) + (-2) = -11
        """
        # Define the axis moving directions dictionary
        POSITIVE = 'positive'
        NEGATIVE = 'negative'
        AXIS_MOVING_DIRECTIONS = {
            GV.LR: {AXIS.X: POSITIVE},
            GV.RL: {AXIS.X: NEGATIVE},
            GV.TB: {AXIS.Y: POSITIVE},
            GV.BT: {AXIS.Y: NEGATIVE},
            GV.CR: {AXIS.X: POSITIVE},
            GV.CL: {AXIS.X: NEGATIVE},
            GV.CB: {AXIS.Y: POSITIVE},
            GV.CT: {AXIS.Y: NEGATIVE},
            GV.BLTR: {AXIS.X: POSITIVE, AXIS.Y: NEGATIVE},
            GV.BRTL: {AXIS.X: NEGATIVE, AXIS.Y: NEGATIVE},
            GV.TRBL: {AXIS.X: NEGATIVE, AXIS.Y: POSITIVE},
            GV.TLBR: {AXIS.X: POSITIVE, AXIS.Y: POSITIVE},
        }

        axis_moving_directions = AXIS_MOVING_DIRECTIONS.get(direction)
        func_positive = lambda n: n > 0
        func_negative = lambda n: n < 0
        reversed_functions = {POSITIVE: func_negative, NEGATIVE: func_positive}
        displacement_dict = self.get_displacement(target_slot)
        reversed_motions = {}
        for axis in AXIS.LIST:
            axis_moving_direction = axis_moving_directions.get(axis)
            if axis_moving_direction is None:
                continue
            displacement = displacement_dict[axis]
            displacement_segment = self._get_segments(displacement,
                                                      segment_flag, ratio)
            reversed_func = reversed_functions[axis_moving_direction]
            reversed_motions[axis] = sum(filter(reversed_func,
                                                displacement_segment))
        return reversed_motions

    def get_num_packets(self, target_slot):
        """Get the number of packets in the target slot."""
        list_x, list_y = self.get_x_y(target_slot)
        return len(list_x)

    def get_report_rate(self):
        """Get the report rate of the packets in Hz."""
        first_sync_event = self.packets[0][-1]
        first_sync_time = first_sync_event.get(MTB.EV_TIME)
        last_sync_event = self.packets[-1][-1]
        last_sync_time = last_sync_event.get(MTB.EV_TIME)
        duration = last_sync_time - first_sync_time
        num_packets = len(self.packets) - 1
        report_rate = float(num_packets) / duration
        return report_rate

    def _call_check_event_func(self, event, expected_value, check_event_result,
                               check_event_func):
        """Call all functions in check_event_func and return the results.

        Note that since check_event_result is a dictionary, it is passed
        by reference.
        """
        for func in check_event_func:
            if func(event):
                event_value = event[MTB.EV_VALUE]
                check_event_result[func] = (event_value == expected_value)
                break

    def _get_event_cycles(self, check_event_func):
        """A generic method to get the number of event cycles.

        For a tap, its event cycle looks like:
            (1) finger touching the touch device:
                BTN_TOOL_FINGER: 0-> 1
                BTN_TOUCH: 0 -> 1
            (2) finger leaving the touch device:
                BTN_TOOL_FINGER: 1-> 0
                BTN_TOUCH: 1 -> 0

        For a one-finger physical click, its event cycle looks like:
            (1) finger clicking and pressing:
                BTN_LEFT : 0-> 1
                BTN_TOOL_FINGER: 0-> 1
                BTN_TOUCH: 0 -> 1
            (2) finger leaving:
                BTN_LEFT : 1-> 0
                BTN_TOOL_FINGER: 1-> 0
                BTN_TOUCH: 1 -> 0

        This method counts how many such cycles there are in the packets.
        """
        # Initialize all check_event_result to False
        # when all_events_observed is False and all check_event_result are True
        #      => all_events_observed is set to True
        # when all_events_observed is True and all check_event_result are True
        #      => all_events_observed is set to False, and
        #         count is increased by 1
        check_event_result = self._init_dict(check_event_func, False)
        all_events_observed = False
        count = 0
        for packet in self.packets:
            for event in packet:
                if all_events_observed:
                    expected_value = 0
                    self._call_check_event_func(event, expected_value,
                                                check_event_result,
                                                check_event_func)
                    if all(check_event_result.values()):
                        all_events_observed = False
                        check_event_result = self._init_dict(check_event_func,
                                                             False)
                        count += 1
                else:
                    expected_value = 1
                    self._call_check_event_func(event, expected_value,
                                                check_event_result,
                                                check_event_func)
                    if all(check_event_result.values()):
                        all_events_observed = True
                        check_event_result = self._init_dict(check_event_func,
                                                             False)
        return count

    def _get_event_cycles_for_num_fingers(self, num_fingers):
        return self._get_event_cycles(self.check_event_func_list[num_fingers])

    def verify_exact_number_fingers_touch(self, num_fingers):
        """Verify the exact number of fingers touching the device.

        Example: for a two-finger touch
            2-finger touch cycles should be equal to 1
            3/4/5-finger touch cycles should be equal to 0
            Don't care about 1-finger touch cycles which is not deterministic.
        """
        range_fingers = range(1, self.MAX_FINGERS)
        flag_check = self._init_dict(range_fingers, True)
        for f in range_fingers:
            cycles = self._get_event_cycles_for_num_fingers(f)
            if f == num_fingers:
                flag_check[f] = cycles == 1
            elif f > num_fingers:
                flag_check[f] = cycles == 0
        return all(flag_check)

    def get_physical_clicks(self, num_fingers):
        """Get the count of physical clicks for the given number of fingers."""
        flag_fingers_touch = self.verify_exact_number_fingers_touch(num_fingers)
        click_cycles = self._get_event_cycles(self.check_event_func_click)
        return click_cycles if flag_fingers_touch else 0


class MtbParser:
    """Touch device MTB event Parser."""

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
            ev_dict[MTB.EV_TIME] = float(result.group(1))
            ev_dict[MTB.EV_TYPE] = int(result.group(2))
            ev_dict[MTB.EV_CODE] = int(result.group(3))
            ev_dict[MTB.EV_VALUE] = int(result.group(4))
        return ev_dict

    def _get_event_dict_SYN_REPORT(self, line):
        """Construct the event dictionary for a SYN_REPORT event."""
        result = self.event_re_patt_SYN_REPORT.search(line)
        ev_dict = {}
        if result is not None:
            ev_dict[MTB.EV_TIME] = float(result.group(1))
            ev_dict[MTB.SYN_REPORT] = True
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
        return ev_dict.get(MTB.SYN_REPORT, False)

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
        packets = MtbParser().parse(event_file)
    for packet in packets:
        print make_pretty_packet(packet)
