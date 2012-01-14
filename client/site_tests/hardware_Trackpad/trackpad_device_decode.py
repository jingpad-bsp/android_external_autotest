# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A module for extracting trackpad device file properties"""

import os
import sys

sys.path.append('/usr/local/autotest/bin/input')
from linux_input import *


# Define some constants
X = 'x'
Y = 'y'
XY = 'xy'
MAX_SLOT = 10
EV_GROUP_TC = 'type-code'
EV_GROUP_TCV = 'type-code-value'


class TrackpadDeviceDecode:
    """Decode trackpad device events."""

    def __init__(self):
        self._init_event_type_code()
        self._init_event_structure()
        self._init_event_name_dict()
        self._init_axis_dict()
        self._init_motion_sep_list()
        self._init_hidden_event_list()

    def _init_axis_dict(self):
        self.axis_dict = {self.abs_mt_x: X,
                          self.abs_mt_y: Y
                         }

    def _init_motion_sep_list(self):
        self.motion_sep_list = [
            self.finger_on,
            self.finger_off,
            self.mouse_click_press,
            self.mouse_click_release,
            self.two_fingers_on,
            self.three_fingers_on,
            self.four_fingers_on,
        ]

    def _init_hidden_event_list(self):
        self.hidden_event_list = [
            self.one_finger_off,
            self.two_fingers_off,
            self.three_fingers_off,
            self.four_fingers_off
        ]

    def _init_event_type_code(self):
        """Initialize event type and code."""
        self.ev_format = ev_format = '%04x'
        self.tcv_format = '%s %s'
        self.max_slot = MAX_SLOT

        # Event types
        self.EV_SYN = ev_format % EV_SYN
        self.EV_KEY = ev_format % EV_KEY
        self.EV_ABS = ev_format % EV_ABS

        # Event codes for synchronization event
        self.SYN_REPORT = ev_format % SYN_REPORT

        # Event codes for absolute axes
        self.ABS_MT_SLOT = ev_format % ABS_MT_SLOT
        self.ABS_MT_TRACKING_ID = ev_format % ABS_MT_TRACKING_ID

        # Event codes for keys and buttons
        self.BTN_MOUSE = ev_format % BTN_MOUSE
        self.BTN_TOUCH = ev_format % BTN_TOUCH
        self.BTN_TOOL_FINGER = ev_format % BTN_TOOL_FINGER
        self.BTN_TOOL_DOUBLETAP = ev_format % BTN_TOOL_DOUBLETAP
        self.BTN_TOOL_TRIPLETAP = ev_format % BTN_TOOL_TRIPLETAP
        self.BTN_TOOL_QUADTAP = ev_format % BTN_TOOL_QUADTAP

        # Event codes for keys and buttons
        self.ABS_X = ev_format % ABS_X
        self.ABS_Y = ev_format % ABS_Y
        self.ABS_PRESSURE = ev_format % ABS_PRESSURE
        self.ABS_MT_SLOT = ev_format % ABS_MT_SLOT
        self.ABS_MT_POSITION_X = ev_format % ABS_MT_POSITION_X
        self.ABS_MT_POSITION_Y = ev_format % ABS_MT_POSITION_Y
        self.ABS_MT_TRACKING_ID = ev_format % ABS_MT_TRACKING_ID
        self.ABS_MT_PRESSURE = ev_format % ABS_MT_PRESSURE

    def _init_event_structure(self):
        ev_type_code = '%s %s'
        ev_struct = '%s %s %d'
        self.finger_on = ev_struct % (self.EV_KEY, self.BTN_TOUCH, 1)
        self.finger_off = ev_struct % (self.EV_KEY, self.BTN_TOUCH, 0)
        self.mouse_click_press = ev_struct % (self.EV_KEY, self.BTN_MOUSE, 1)
        self.mouse_click_release = ev_struct % (self.EV_KEY, self.BTN_MOUSE, 0)
        self.one_finger_on = ev_struct % (self.EV_KEY, self.BTN_TOOL_FINGER, 1)
        self.one_finger_off = ev_struct % (self.EV_KEY, self.BTN_TOOL_FINGER, 0)
        self.two_fingers_on = ev_struct % (self.EV_KEY,
                                           self.BTN_TOOL_DOUBLETAP, 1)
        self.two_fingers_off = ev_struct % (self.EV_KEY,
                                            self.BTN_TOOL_DOUBLETAP, 0)
        self.three_fingers_on = ev_struct % (self.EV_KEY,
                                             self.BTN_TOOL_TRIPLETAP, 1)
        self.three_fingers_off = ev_struct % (self.EV_KEY,
                                              self.BTN_TOOL_TRIPLETAP, 0)
        self.four_fingers_on = ev_struct % (self.EV_KEY,
                                            self.BTN_TOOL_QUADTAP, 1)
        self.four_fingers_off = ev_struct % (self.EV_KEY,
                                             self.BTN_TOOL_QUADTAP, 0)
        self.tracking_id = ev_type_code % (self.EV_ABS, self.ABS_MT_TRACKING_ID)
        self.slot = ev_type_code % (self.EV_ABS, self.ABS_MT_SLOT)
        self.abs_mt_x = ev_type_code % (self.EV_ABS, self.ABS_MT_POSITION_X)
        self.abs_mt_y = ev_type_code % (self.EV_ABS, self.ABS_MT_POSITION_Y)
        self.abs_mt_z = ev_type_code % (self.EV_ABS, self.ABS_MT_PRESSURE)
        self.abs_x = ev_type_code % (self.EV_ABS, self.ABS_X)
        self.abs_y = ev_type_code % (self.EV_ABS, self.ABS_Y)
        self.abs_z = ev_type_code % (self.EV_ABS, self.ABS_PRESSURE)
        self.ev_syn = ev_type_code % (self.EV_SYN, self.SYN_REPORT)

    def _init_event_name_dict(self):
        self.event_name_dict = {
            self.finger_on: 'Finger on',
            self.finger_off: 'Finger off',
            self.mouse_click_press: 'Mouse click press',
            self.mouse_click_release: 'Mouse click release',
            self.one_finger_on: 'One finger on',
            self.one_finger_off: 'One finger off',
            self.two_fingers_on: 'Two fingers on',
            self.two_fingers_off: 'Two fingers off',
            self.three_fingers_on: 'Three fingers on',
            self.three_fingers_off: 'Three fingers off',
            self.four_fingers_on: 'Four fingers on',
            self.four_fingers_off: 'Four fingers off',
            self.tracking_id: 'Tracking ID',
            self.slot: 'Slot',
            self.abs_mt_x: 'Abs mt x',
            self.abs_mt_y: 'Abs mt y',
            self.abs_mt_z: 'Abs mt z',
            self.abs_x: 'Abs x',
            self.abs_y: 'Abs y',
            self.abs_z: 'Abs z',
            self.ev_syn: 'SYN',
        }

    def _get_axis(self, tc):
        return self.axis_dict[tc]

    def _calc_accu_motion(self, slot, axis, evalue):
        value = int(evalue)
        s = slot
        if self.prev_pos[s][axis] is not None:
            motion = abs(value - self.prev_pos[s][axis])
            self.accu_motion[s][axis] += motion
            self.accu_motion[s][XY] += motion
        self.prev_pos[s][axis] = value

    def _reset_accu_motion(self, slot=None):
        slots = range(self.max_slot) if slot is None else [slot]
        for s in slots:
            self.accu_motion[s][X] = 0
            self.accu_motion[s][Y] = 0
            self.accu_motion[s][XY] = 0

    def _reset_accu_pos(self, slot=None):
        slots = range(self.max_slot) if slot is None else [slot]
        for s in slots:
            self.prev_pos[s][X] = None
            self.prev_pos[s][Y] = None

    def _reset_time(self):
        self.time_finger_on = None
        self.time_finger_off = None

    def _calc_timespan(self, bgn_time, end_time):
        if bgn_time is None or end_time is None:
            return None
        else:
            timespan = float(end_time) - float(bgn_time)
            return timespan

    def _init_pos_and_motion(self):
        self.prev_pos = {}
        self.accu_motion = {}
        for s in range(self.max_slot):
            self.prev_pos[s] = {}
            self.accu_motion[s] = {}
        self._reset_accu_pos()
        self._reset_accu_motion()

    def _output_append_motion(self, slot):
        if self.accu_motion[slot][XY] > 0:
            self.output.append(self.motion_format % (slot,
                               self.accu_motion[slot][X],
                               self.accu_motion[slot][Y],
                               self.accu_motion[slot][XY]))

    def _output_append_event(self, group, data, evalue=None):
        event_str = None
        is_finger_on = False
        if group == EV_GROUP_TCV:
            tcv = data
            is_finger_on = tcv == self.finger_on
            if tcv not in self.hidden_event_list:
                if is_finger_on:
                    prefix = '\n'
                elif tcv == self.finger_off:
                    prefix = ''
                else:
                    prefix = '  '
                event_str = prefix + self.event_name_dict[tcv]
        elif group == EV_GROUP_TC:
            tc = data
            event_str = ('      ' + self.tcv_format %
                         (self.event_name_dict[tc], evalue))

        # If finger_on event does not appear yet, save the event_str so
        # that it can be appended to the output after the finger_on event.
        if event_str is not None:
            if self.time_finger_on is None:
                self.output_buffer.append(event_str)
            else:
                self.output.append(event_str)

        # Flush any previous event_str stored in output_buffer to output
        # if this data is a finger_on event
        if is_finger_on:
            for e in self.output_buffer:
                self.output.append(e)
            self.output_buffer = []

    def _output_append_time(self, timespan):
        if timespan is None:
            self.output.append('  warning: finger on event was missing!')
        else:
            msg = '  timespan for whole finger on period: %f seconds'
            self.output.append(msg % timespan)

    def decode_device_events(self, file_name):
        """Decode the device event file."""
        if not os.path.isfile(file_name):
            print ('Warning: the device event file "%s" does not exist.' %
                   file_name)
            return
        print '\n\n%s' % ('-' * 60)
        print 'Decoding %s ...' % file_name

        self.output = []
        self.output_buffer = []
        self._init_pos_and_motion()
        slot = 0
        motion_format = ('      accu_motion[%d]: x = %d, y = %d, ' 'xy = %d')
        self.motion_format = motion_format
        self._reset_time()

        with open(file_name) as f:
            for line in f:
                # print 'Decode line: ', line
                header, timestamp, etype, ecode, evalue = line.split()
                tc = '%s %s' % (etype, ecode)
                tcv = '%s %s %s' % (etype, ecode, evalue)

                # Output accumulated motion if current event is in the
                # motion_sep_list, e.g., mouse_click_press, two_fingers_on, etc.
                if tcv in self.motion_sep_list:
                    for s in range(self.max_slot):
                        self._output_append_motion(s)
                    self._reset_accu_motion()

                if tcv == self.finger_on:
                    self.time_finger_on = timestamp

                if tcv == self.finger_off:
                    self._reset_accu_pos()
                    self._reset_accu_motion()
                    self.time_finger_off = timestamp
                    timespan = self._calc_timespan(self.time_finger_on,
                                                   self.time_finger_off)
                    self._output_append_time(timespan)

                if tcv in self.event_name_dict:
                    self._output_append_event(EV_GROUP_TCV, tcv)

                elif tc in self.event_name_dict:
                    if tc == self.slot:
                        slot = int(evalue)

                    elif tc == self.tracking_id and evalue == '-1':
                        self._output_append_motion(slot)
                        self._reset_accu_pos(slot)
                        self._reset_accu_motion(slot)

                    elif tc in self.axis_dict:
                        self._calc_accu_motion(slot, self._get_axis(tc), evalue)

                if tcv == self.finger_off:
                    self._reset_time()

        for line in self.output:
            print line


if __name__ == '__main__':
    tdd = TrackpadDeviceDecode()
    tdd.decode_device_events(sys.argv[1])
