# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A wrapper for robot manipulation with Touchbot II."""

import math
import os
import re
import sys
import time

import common_util
import test_conf as conf

from firmware_constants import GV, MODE


# Define the robot control script names.
SCRIPT_LINE = 'line.py'
SCRIPT_TAP = 'tap.py'
SCRIPT_CLICK = 'click.py'
SCRIPT_ONE_STATIONARY_FINGER = 'one_stationary_finger.py'
SCRIPT_STATIONARY_WITH_TAPS = 'stationary_finger_with_taps_around_it.py'

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
ABOVE_CENTER = 0.25
BELOW_CENTER = 0.75
LEFT_TO_CENTER = 0.25
RIGHT_TO_CENTER = 0.75

OUTER_PINCH_SPACING = 70
INNER_PINCH_SPACING = 25

PHYSICAL_CLICK_SPACING = 20

TWO_CLOSE_FINGER_SPACING = 17
TWO_FINGER_SPACING = 25

class RobotWrapperError(Exception):
    """An exception class for the robot_wrapper module."""
    pass


class RobotWrapper:
    """A class to wrap and manipulate the robot library."""

    def __init__(self, board, mode, is_touchscreen, should_calibrate=True):
        self._board = board
        self._mode = mode
        self.is_touchscreen = is_touchscreen
        self._robot_script_dir = self._get_robot_script_dir()

        # Each get_contorol_command method maps to a script name.
        self._robot_script_name_dict = {
            self._get_control_command_line: SCRIPT_LINE,
            self._get_control_command_rapid_taps: SCRIPT_TAP,
            self._get_control_command_single_tap: SCRIPT_TAP,
            self._get_control_command_drumroll: SCRIPT_TAP,
            self._get_control_command_click: SCRIPT_CLICK,
            self._get_control_command_one_stationary_finger:
                    SCRIPT_ONE_STATIONARY_FINGER,
            self._get_control_command_pinch: SCRIPT_LINE,
            self._get_control_command_stationary_with_taps:
                    SCRIPT_STATIONARY_WITH_TAPS,
        }

        # Each gesture maps to a get_contorol_command method
        self._method_of_control_command_dict = {
            conf.ONE_FINGER_TRACKING: self._get_control_command_line,
            conf.ONE_FINGER_TO_EDGE: self._get_control_command_line,
            conf.ONE_FINGER_SWIPE: self._get_control_command_line,
            conf.ONE_FINGER_TAP: self._get_control_command_single_tap,
            conf.ONE_FINGER_TRACKING_FROM_CENTER:
                    self._get_control_command_line,
            conf.RAPID_TAPS: self._get_control_command_rapid_taps,
            conf.TWO_FINGER_TRACKING: self._get_control_command_line,
            conf.TWO_FINGER_SWIPE: self._get_control_command_line,
            conf.TWO_FINGER_TAP: self._get_control_command_single_tap,
            conf.TWO_CLOSE_FINGERS_TRACKING: self._get_control_command_line,
            conf.RESTING_FINGER_PLUS_2ND_FINGER_MOVE:
                    self._get_control_command_one_stationary_finger,
            conf.FINGER_CROSSING:
                    self._get_control_command_one_stationary_finger,
            conf.PINCH_TO_ZOOM: self._get_control_command_pinch,
            conf.DRUMROLL: self._get_control_command_drumroll,
            conf.ONE_FINGER_PHYSICAL_CLICK: self._get_control_command_click,
            conf.TWO_FINGER_PHYSICAL_CLICK: self._get_control_command_click,
            conf.THREE_FINGER_PHYSICAL_CLICK: self._get_control_command_click,
            conf.FOUR_FINGER_PHYSICAL_CLICK: self._get_control_command_click,
            conf.STATIONARY_FINGER_NOT_AFFECTED_BY_2ND_FINGER_TAPS:
                    self._get_control_command_stationary_with_taps,
        }

        self._line_dict = {
            GV.LR: (START, CENTER, END, CENTER),
            GV.RL: (END, CENTER, START, CENTER),
            GV.TB: (CENTER, START, CENTER, END),
            GV.BT: (CENTER, END, CENTER, START),
            GV.BLTR: (START, END, END, START),
            GV.TRBL: (END, START, START, END),
            GV.BRTL: (END, END, START, START),
            GV.TLBR: (START, START, END, END),
            GV.CUR: (CENTER, CENTER, END, START),
            GV.CUL: (CENTER, CENTER, START, START),
            GV.CLR: (CENTER, CENTER, END, END),
            GV.CLL: (CENTER, CENTER, START, END),

            # Overshoot for this one-finger gesture only: ONE_FINGER_TO_EDGE
            GV.CL: (CENTER, CENTER, OFF_START, CENTER),
            GV.CR: (CENTER, CENTER, OFF_END, CENTER),
            GV.CT: (CENTER, CENTER, CENTER, OFF_START),
            GV.CB: (CENTER, CENTER, CENTER, OFF_END),
        }

        # The angle wrt the pad that the fingers should take when doing a 2f
        # gesture along these lines.
        self._angle_dict = {
            GV.LR: -45,
            GV.RL: -45,
            GV.TB: 45,
            GV.BT: 45,
            GV.TLBR: 90,
            GV.BLTR: 0,
            GV.TRBL: 0,
        }

        # The stationary finger locations corresponding the line specifications
        # for the finger crossing tests
        self._stationary_finger_dict = {
            GV.LR: (CENTER, ABOVE_CENTER),
            GV.RL: (CENTER, BELOW_CENTER),
            GV.TB: (RIGHT_TO_CENTER, CENTER),
            GV.BT: (LEFT_TO_CENTER, CENTER),
            GV.BLTR: (RIGHT_TO_CENTER, BELOW_CENTER),
            GV.TRBL: (LEFT_TO_CENTER, ABOVE_CENTER),
        }

        self._speed_dict = {
            GV.SLOW: 10,
            GV.NORMAL: 20,
            GV.FAST: 30,
        }

        self._location_dict = {
            # location parameters for one-finger taps
            GV.TL: (START, START),
            GV.TR: (END, START),
            GV.BL: (START, END),
            GV.BR: (END, END),
            GV.TS: (CENTER, START),
            GV.BS: (CENTER, END),
            GV.LS: (START, CENTER),
            GV.RS: (END, CENTER),
            GV.CENTER: (CENTER, CENTER),

            # location parameters for
            #   stationary_finger_not_affected_by_2nd_finger_taps
            GV.AROUND: (
                CENTER, START,
                RIGHT_TO_CENTER, ABOVE_CENTER,
                END, CENTER,
                RIGHT_TO_CENTER, BELOW_CENTER,
                CENTER, END,
            ),

            # location parameters for two-finger taps
            #   In the manual mode:
            #     The original meanings of the following gesture variations:
            #       HORIZONTAL: two fingers aligned horizontally
            #       VERTICAL: two fingers aligned vertically
            #       DIAGONAL: two fingers aligned diagonally
            #
            #   In the robot mode:
            #     The robot fingers cannot rotate automatically. Have the robot
            #     perform taps on distinct locations instead for convenience.
            #     Note: the location is specified by the first finger, and the
            #           second finger is on the left. Choose the tap locations
            #           that guarantee both fingers on the touch surface.
            GV.HORIZONTAL: (CENTER, CENTER),
            GV.VERTICAL: (END, CENTER),
            GV.DIAGONAL: (CENTER, END),

            # location parameters for one_finger_click and two_finger_click
            None: (CENTER, CENTER),
        }

        self.fingertip_size = 2
        self.fingertips = [None, None, None, None]

        self._build_robot_script_paths()

        if should_calibrate:
            self._calibrate_device(board)

    def get_fingertips(self, size):
        script = os.path.join(self._robot_script_dir,
                              'manipulate_fingertips.py')
        cmd = ('python %s %d %d %d %d %d %s' %
                 (script, 1, 1, 1, 1, size, str(True)))
        if self._execute_control_command(cmd):
            raise RobotWrapperError('Error getting the fingertips!')
        self.fingertip_size = size
        self.fingertips = [size, size, size, size]

    def return_fingertips(self):
        script = os.path.join(self._robot_script_dir,
                              'manipulate_fingertips.py')
        cmd = ('python %s %d %d %d %d %d %s' %
                 (script, 1, 1, 1, 1, self.fingertip_size, str(False)))
        if self._execute_control_command(cmd):
            raise RobotWrapperError('Error returning the fingertips!')
        self.fingertips = [None, None, None, None]

    def _calibrate_device(self, board):
        """ Have the operator show the robot where the device is."""
        calib_script = os.path.join(self._robot_script_dir,
                                    'calibrate_for_new_device.py')
        calib_cmd = 'python %s %s' % (calib_script, board)
        self._execute_control_command(calib_cmd)

    def _is_robot_action_mode(self):
        """Is it in robot action mode?

        In the robot action mode, it actually invokes the robot control script.
        """
        return self._mode in [MODE.ROBOT]

    def _raise_error(self, msg):
        """Only raise an error if it is in the robot action mode."""
        if self._is_robot_action_mode():
            raise RobotWrapperError(msg)

    def _get_robot_script_dir(self):
        """Get the directory of the robot control scripts."""
        cmd = 'find %s -type d -name %s' % (conf.robot_lib_path,
                                            conf.python_package)
        path = common_util.simple_system_output(cmd)
        if path:
            robot_script_dir = os.path.join(path, conf.gestures_sub_path)
            if os.path.isdir(robot_script_dir):
                return robot_script_dir
        return ''

    def _get_num_taps(self, gesture):
        """Determine the number of times to tap."""
        matches = re.match('[^0-9]*([0-9]*)[^0-9]*', gesture)
        return int(matches.group(1)) if matches else None

    def _reverse_coord_if_is_touchscreen(self, coordinates):
        """Reverse the coordinates if the device is a touchscreen.

        E.g., the original coordinates = (0.1, 0.9)
              After reverse, the coordinates = (1 - 0.1, 1 - 0.9) = (0.9, 0.1)

        @param coordinates: a tuple of coordinates
        """
        return (tuple(1.0 - c for c in coordinates) if self.is_touchscreen else
                coordinates)

    def _get_control_command_pinch(self, robot_script, gesture, variation):
        # Depending on which direction you're zooming, change the order of the
        # finger spacings.
        if GV.ZOOM_IN in variation:
            starting_spacing = INNER_PINCH_SPACING
            ending_spacing = OUTER_PINCH_SPACING
        else:
            starting_spacing = OUTER_PINCH_SPACING
            ending_spacing = INNER_PINCH_SPACING

        # Keep the hand centered on the pad, and make the fingers move
        # in or out with only two opposing fingers on the pad.
        para = (robot_script, self._board,
                CENTER, CENTER, 45, starting_spacing,
                CENTER, CENTER, 45, ending_spacing,
                0, 1, 0, 1, self._speed_dict[GV.SLOW], 'basic')
        return 'python %s %s_min.p %f %f %d %d %f %f %d %d %d %d %d %d %f %s' % para

    def _get_control_command_one_stationary_finger(self, robot_script, gesture,
                                                   variation):
        line = speed = None
        # The stationary finger should be in the bottom left corner for resting
        # finger tests, and various locations for finger crossing tests
        stationary_finger = (START, END)

        for element in variation:
            if element in GV.GESTURE_DIRECTIONS:
                line = self._line_dict[element]
                if 'finger_crossing' in gesture:
                    stationary_finger = self._stationary_finger_dict[element]
            elif element in GV.GESTURE_SPEED:
                speed = self._speed_dict[element]

        if line is None or speed is None:
            msg = 'Cannot derive the line/speed parameters from %s %s.'
            self._raise_error(msg % (gesture, variation))

        line = self._reverse_coord_if_is_touchscreen(line)
        start_x, start_y, end_x, end_y = line
        stationary_x, stationary_y = stationary_finger

        para = (robot_script, self._board, stationary_x, stationary_y,
                start_x, start_y, end_x, end_y, speed)
        cmd = 'python %s %s_min.p %f %f %f %f %f %f %s' % para
        return cmd

    def _get_control_command_line(self, robot_script, gesture, variation):
        """Get robot control command for gestures using robot line script."""
        line_type = 'swipe' if bool('swipe' in gesture) else 'basic'
        line = speed = finger_angle = None
        for element in variation:
            if element in GV.GESTURE_DIRECTIONS:
                line = self._line_dict[element]
                finger_angle = self._angle_dict.get(element, None)
            elif element in GV.GESTURE_SPEED:
                speed = self._speed_dict[element]

        if line_type is 'swipe' and speed is None:
            speed = self._speed_dict[GV.FAST]

        if 'two_close_fingers' in gesture and speed is None:
            speed = self._speed_dict[GV.NORMAL]

        if line is None or speed is None:
            msg = 'Cannot derive the line/speed parameters from %s %s.'
            self._raise_error(msg % (gesture, variation))

        line = self._reverse_coord_if_is_touchscreen(line)
        start_x, start_y, end_x, end_y = line

        if 'two' in gesture:
            if 'close_fingers' in gesture:
                finger_spacing = TWO_CLOSE_FINGER_SPACING
                finger_angle += 45
                fingers = (1, 1, 0, 0)
            else:
                finger_spacing = TWO_FINGER_SPACING
                fingers = (0, 1, 0, 1)

            if finger_angle is None:
                msg = 'Unable to determine finger angle for %s %s.'
                self._raise_error(msg % (gesture, variation))
        else:
            finger_spacing = 17
            fingers = (0, 1, 0, 0)
            finger_angle = 0

        para = (robot_script, self._board,
                start_x, start_y, finger_angle, finger_spacing,
                end_x, end_y, finger_angle, finger_spacing,
                fingers[0], fingers[1], fingers[2], fingers[3],
                speed, line_type)
        cmd = 'python %s %s.p %f %f %d %d %f %f %d %d %d %d %d %d %f %s' % para
        return cmd

    def _get_control_command_stationary_with_taps(self, robot_script, gesture,
                                                  variation):
        """ There is only one variant of this gesture, so there is only one
        command to generate.  This is the command for tapping around a
        stationary finger on the pad.
        """
        return 'python %s %s.p 0.5 0.5' % (robot_script, self._board)

    def _get_control_command_rapid_taps(self, robot_script, gesture, variation):
        num_taps = self._get_num_taps(gesture)
        return self._get_control_command_taps(robot_script, gesture,
                                              variation, num_taps)

    def _get_control_command_single_tap(self, robot_script, gesture, variation):
        return self._get_control_command_taps(robot_script, gesture,
                                              variation, 1)

    def _get_control_command_drumroll(self, robot_script, gesture, variation):
        """Get robot control command for the drumroll gesture. There is only
        one so there is no need for complicated parsing here.
        """
        return ('python %s %s.p 0.5 0.5 45 20 0 1 0 1 50 drumroll' %
                (robot_script, self._board))

    def _get_control_command_taps(self, robot_script, gesture,
                                  variation, num_taps):
        """Get robot control command for tap gestures.  This includes rapid tap
        tests as well as 1 and 2 finger taps at various locations on the pad.
        """
        if num_taps is None:
            msg = 'Cannot determine the number of taps to do from %s.'
            self._raise_error(msg % gesture)

        # The tap commands have identical arguments as the click except with
        # two additional arguments at the end.  As such we generate the 'click'
        # command and add these on to make it work as a tap.
        cmd = self._get_control_command_click(robot_script, gesture, variation)
        control_cmd = '%s %d tap' % (cmd, num_taps)
        return control_cmd

    def _get_control_command_click(self, robot_script, gesture, variation):
        """Get robot control command for pysical click gestures """
        location = None
        for element in variation:
            location = self._location_dict.get(element)
            if location:
                location_str = ' '.join(
                    map(str, self._reverse_coord_if_is_touchscreen(location)))
                break

        if location is None:
            msg = 'Cannot determine the location parameters from %s %s.'
            self._raise_error(msg % (gesture, variation))

        fingers = [1, 0, 0, 0]
        if 'two' in gesture:
            fingers = [0, 1, 0, 1]
        elif 'three' in gesture:
            fingers = [0, 1, 1, 1]
        elif 'four' in gesture:
            fingers = [1, 1, 1, 1]

        para = (robot_script, self._board, location_str, 45,
                PHYSICAL_CLICK_SPACING,
                fingers[0], fingers[1], fingers[2], fingers[3])
        control_cmd = 'python %s %s.p %s %d %d %d %d %d %d' % para
        return control_cmd

    def _build_robot_script_paths(self):
        """Build the robot script paths."""
        # Check if the robot script dir could be found.
        if not self._robot_script_dir:
            script_path = os.path.join(conf.robot_lib_path, conf.python_package,
                                       conf.gestures_sub_path)
            msg = 'Cannot find robot script directory in "%s".'
            self._raise_error(msg % script_path)

        # Build the robot script path dictionary
        self._robot_script_dict = {}
        for method in self._robot_script_name_dict:
            script_name = self._robot_script_name_dict.get(method)

            # Check if the control script actually exists.
            robot_script = os.path.join(self._robot_script_dir, script_name)
            if not os.path.isfile(robot_script):
                msg = 'Cannot find the robot control script: %s'
                self._raise_error(msg % robot_script)

            self._robot_script_dict[method] = robot_script

    def _get_control_command(self, gesture, variation):
        """Get robot control command based on the gesture and variation."""
        script_method = self._method_of_control_command_dict.get(gesture)
        if not script_method:
            self._raise_error('Cannot find "%s" gesture in '
                              '_method_of_control_command_dict.' % gesture)

        robot_script = self._robot_script_dict.get(script_method)
        if not robot_script:
            msg = 'Cannot find "%s" method in _robot_script_dict.'
            self._raise_error(msg % script_method)

        return script_method(robot_script, gesture, variation)

    def _execute_control_command(self, control_cmd):
        """Execute a control command."""
        print 'Executing: "%s"' % control_cmd
        if self._is_robot_action_mode():
            # Pausing to give everything time to settle
            time.sleep(2)
            return common_util.simple_system(control_cmd)
        return 0

    def control(self, gesture, variation):
        """Have the robot perform the gesture variation."""
        if (gesture.name in conf.robot_must_start_without_fingertips
            and self.fingertips != [None, None, None, None]):
            self.return_fingertips()
        elif (gesture.name not in conf.robot_must_start_without_fingertips
              and self.fingertips == [None, None, None, None]):
            self.get_fingertips(self.fingertip_size)

        if not isinstance(variation, tuple):
            variation = (variation,)
        try:
            print gesture.name, variation
            control_cmd = self._get_control_command(gesture.name, variation)
            print control_cmd
            self._execute_control_command(control_cmd)
        except RobotWrapperError as e:
            print gesture.name, variation
            print 'RobotWrapperError: %s' % str(e)
            sys.exit(1)
