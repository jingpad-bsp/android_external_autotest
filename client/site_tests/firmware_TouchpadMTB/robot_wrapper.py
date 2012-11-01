# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A wrapper for robot manipulation."""

import os

import common_util
import test_conf as conf

from firmware_constants import GV


# Define the robot control script names.
SCRIPT_LINE = 'line.py'
SCRIPT_CLICK = 'click.py'

# Define constants for coordinates.
# Normally, a gesture is performed within [START, END].
# For tests involved with RangeValidator which intends to verify
# the min/max reported coordinates, use [OFF_START, OFF_END] instead
# so that the gestures are performed off the edge.
START = 0.1
CENTER = 0.5
END = 0.9
OFF_START = -0.05
OFF_END = 1.05

# Define constants used to determine the types of gestures.
TRACKING = 'tracking'

# Define constants used as command options of robot control scripts.
#   For line gesture: [basic | swipe]
#   For click gesture: [click | tap]
BASIC = 'basic'
SWIPE = 'swipe'
TAP = 'tap'
CLICK = 'click'


class RobotWrapperError(Exception):
    """An exception class for the robot_wrapper module."""
    pass


class RobotWrapper:
    """A class to wrap and manipulate the robot library."""

    def __init__(self, board):
        self._board = board
        self._robot_script_dir = self._get_robot_script_dir()

        self._robot_script_name_dict = {
            conf.ONE_FINGER_TRACKING: SCRIPT_LINE,
            conf.ONE_FINGER_SWIPE: SCRIPT_LINE,
            conf.ONE_FINGER_TAP: SCRIPT_CLICK,
            conf.ONE_FINGER_PHYSICAL_CLICK: SCRIPT_CLICK,
        }

        self._method_of_control_command_dict = {
            conf.ONE_FINGER_TRACKING: self._get_control_command_line,
            conf.ONE_FINGER_SWIPE: self._get_control_command_line,
            conf.ONE_FINGER_TAP: self._get_control_command_click,
            conf.ONE_FINGER_PHYSICAL_CLICK: self._get_control_command_click,
        }

        self._line_dict = {
            GV.LR: (OFF_START, CENTER, OFF_END, CENTER),
            GV.RL: (OFF_END, CENTER, OFF_START, CENTER),
            GV.TB: (CENTER, OFF_START, CENTER, OFF_END),
            GV.BT: (CENTER, OFF_END, CENTER, OFF_START),
            GV.BLTR: (START, END, END, START),
            GV.TRBL: (END, START, START, END),
            GV.BRTL: (END, END, START, START),
            GV.TLBR: (START, START, END, END),
        }

        self._speed_dict = {
            GV.SLOW: 33,
            GV.NORMAL: 100,
            GV.FAST: 300,
        }

        self._location_dict = {
            GV.TL: (START, START),
            GV.TR: (END, START),
            GV.BL: (START, END),
            GV.BR: (END, END),
            GV.TS: (CENTER, START),
            GV.BS: (CENTER, END),
            GV.LS: (START, CENTER),
            GV.RS: (END, CENTER),
            GV.CENTER: (CENTER, CENTER),
            None: (CENTER, CENTER),
        }

    def _get_robot_script_dir(self):
        """Get the directory of the robot control scripts."""
        cmd = 'find %s -name %s' % (conf.robot_lib_path, conf.python_package)
        path = common_util.simple_system_output(cmd)
        if path:
            robot_script_dir = os.path.join(path, conf.gestures_sub_path)
            if os.path.isdir(robot_script_dir):
                return robot_script_dir
        return ''

    def _get_basic_tracking_or_swipe(self, gesture):
        """Determine whether the gesture is a basic tracking or a swipe."""
        if SWIPE in gesture:
            return SWIPE
        elif TRACKING in gesture:
            return BASIC
        else:
            return None

    def _get_tap_or_click(self, gesture):
        """Determine whether the gesture is a tap or a click."""
        if TAP in gesture:
            return TAP
        elif CLICK in gesture:
            return CLICK
        else:
            return None

    def _get_control_command_line(self, robot_script, gesture, variation):
        """Get robot control command for gestures using robot line script."""
        # Determine whether this is a basic tracking gesture or a swipe.
        basic_tracking_or_swipe = self._get_basic_tracking_or_swipe(gesture)
        if not basic_tracking_or_swipe:
            msg = 'Cannot determine whether "%s" is basic tracking or swipe.'
            raise RobotWrapperError(msg % gesture)

        line = speed = None
        for element in variation:
            if element in GV.GESTURE_DIRECTIONS:
                line = self._line_dict[element]
            elif element in GV.GESTURE_SPEED:
                speed = self._speed_dict[element]

        # The speed is assigned in the one_finger_tracking gesture.
        # For the swipe gesture, no speed is specified in test_conf.
        # Hence, need to assign FAST to the speed of the swipe gesture.
        if basic_tracking_or_swipe == SWIPE:
            speed = self._speed_dict[GV.FAST]

        if line is None or speed is None:
            msg = 'Cannot derive the line/speed parameters from %s %s.'
            raise RobotWrapperError(msg % (gesture, variation))

        start_x, start_y, end_x, end_y = line
        para = (robot_script, self._board, start_x, start_y, end_x, end_y,
                speed, basic_tracking_or_swipe)
        control_cmd = 'python %s %s %f %f %f %f %f %s' % para
        return control_cmd

    def _get_control_command_click(self, robot_script, gesture, variation):
        """Get robot control command for gestures using robot click script."""
        location = None
        for element in variation:
            location = self._location_dict.get(element)
            if location:
                break

        if location is None:
            msg = 'Cannot derive the location parameters from %s %s.'
            raise RobotWrapperError(msg % (gesture, variation))
        target_x, target_y = location

        tap_or_click = self._get_tap_or_click(gesture)
        if not tap_or_click:
            msg = 'Cannot determine whether "%s" is a tap or a click.'
            raise RobotWrapperError(msg % gesture)

        para = (robot_script, self._board, target_x, target_y, tap_or_click)
        control_cmd = 'python %s %s %f %f %s' % para
        return control_cmd

    def _get_control_command(self, gesture, variation):
        """Get robot control command based on the gesture and variation."""
        # Check if the robot script dir could be found.
        if not self._robot_script_dir:
            script_path = os.path.join(conf.robot_lib_path, conf.python_package,
                                       conf.gestures_sub_path)
            msg = 'Cannot find robot script directory in "%s".'
            raise RobotWrapperError(msg % script_path)

        # Check if there exists a control script for this gesture.
        script_name = self._robot_script_name_dict.get(gesture)
        if not script_name:
            msg = 'Cannot find "%s" gesture in _robot_script_name_dict.'
            raise RobotWrapperError(msg % gesture)

        # Check if the control script actually exists.
        robot_script = os.path.join(self._robot_script_dir, script_name)
        if not os.path.isfile(robot_script):
            msg = 'Cannot find the robot control script: %s'
            raise RobotWrapperError(msg % robot_script)

        # Check if there exists a method to derive the robot script command
        # for this gesture.
        script_method = self._method_of_control_command_dict.get(gesture)
        if not script_method:
            msg = 'Cannot find "%s" gesture in _method_of_control_command_dict.'
            raise RobotWrapperError(msg % gesture)

        return script_method(robot_script, gesture, variation)

    def control(self, gesture, variation):
        """Have the robot perform the gesture variation."""
        if not isinstance(variation, tuple):
            variation = (variation,)
        try:
            control_cmd = self._get_control_command(gesture.name, variation)
            print gesture.name, variation
            print 'Executing: "%s"' % control_cmd
            common_util.simple_system(control_cmd)
        except RobotWrapperError as e:
            print gesture.name, variation
            print 'RobotWrapperError: %s' % str(e)
