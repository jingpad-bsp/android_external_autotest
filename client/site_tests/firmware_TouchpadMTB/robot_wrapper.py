# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A wrapper for robot manipulation."""

import os
import re

import common_util
import test_conf as conf

from firmware_constants import GV, MODE


# Define the robot control script names.
SCRIPT_LINE = 'line.py'
SCRIPT_CLICK = 'click.py'
SCRIPT_RAPID_TAPS = 'rapid_taps.py'
SCRIPT_REPLAY = 'run_program.py'

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
ABOVE_CENTER = 0.3
BELOW_CENTER = 0.7
LEFT_TO_CENTER = 0.3
RIGHT_TO_CENTER = 0.7

# Define constants used to determine the types of gestures.
TRACKING = 'tracking'
CROSSING = 'crossing'
MOVE = 'move'

# Define constants determining which dictionary to use for a gesture
THROUGH_CENTER = 'through_center'
OFF_CENTER = 'off_center'

# Define constants used as command options of robot control scripts.
#   For line gesture: [basic | swipe]
#   For click gesture: [click | tap]
BASIC = 'basic'
SWIPE = 'swipe'
TAP = 'tap'
CLICK = 'click'

CALIBRATION_FILE = 'calibrated_dimensions.py'


class RobotWrapperError(Exception):
    """An exception class for the robot_wrapper module."""
    pass


class RobotWrapper:
    """A class to wrap and manipulate the robot library."""

    def __init__(self, board, mode, should_calibrate=True):
        self._board = board
        self._mode = mode
        self._robot_script_dir = self._get_robot_script_dir()
        self._gesture_variation = None

        # Each get_contorol_command method maps to a script name.
        self._robot_script_name_dict = {
            self._get_control_command_line: SCRIPT_LINE,
            self._get_control_command_click: SCRIPT_CLICK,
            self._get_control_command_rapid_taps: SCRIPT_RAPID_TAPS,
            self._get_control_command_replay: SCRIPT_REPLAY,
        }

        # Each gesture maps to a get_contorol_command method
        self._method_of_control_command_dict = {
            conf.ONE_FINGER_TRACKING: self._get_control_command_line,
            conf.ONE_FINGER_TO_EDGE: self._get_control_command_line,
            conf.ONE_FINGER_SWIPE: self._get_control_command_line,
            conf.ONE_FINGER_TAP: self._get_control_command_click,
            conf.ONE_FINGER_PHYSICAL_CLICK: self._get_control_command_click,
            conf.TWO_FINGER_TRACKING: self._get_control_command_line,
            conf.TWO_FINGER_SWIPE: self._get_control_command_line,
            conf.TWO_FINGER_TAP: self._get_control_command_click,
            conf.TWO_FINGER_PHYSICAL_CLICK: self._get_control_command_click,
            conf.FINGER_CROSSING: self._get_control_command_line,
            conf.STATIONARY_FINGER_NOT_AFFECTED_BY_2ND_FINGER_TAPS:
                    self._get_control_command_click,
            conf.RESTING_FINGER_PLUS_2ND_FINGER_MOVE:
                    self._get_control_command_line,
            conf.RAPID_TAPS: self._get_control_command_rapid_taps,
        }

        self._line_dict = {
            # These are the tracking lines that will go through the center.
            THROUGH_CENTER: {
                GV.LR: (START, CENTER, END, CENTER),
                GV.RL: (END, CENTER, START, CENTER),
                GV.TB: (CENTER, START, CENTER, END),
                GV.BT: (CENTER, END, CENTER, START),
                GV.BLTR: (START, END, END, START),
                GV.TRBL: (END, START, START, END),
                GV.BRTL: (END, END, START, START),
                GV.TLBR: (START, START, END, END),

                # Overshoot for this one-finger gesture only: ONE_FINGER_TO_EDGE
                GV.CL: (CENTER, CENTER, OFF_START, CENTER),
                GV.CR: (CENTER, CENTER, OFF_END, CENTER),
                GV.CT: (CENTER, CENTER, CENTER, OFF_START),
                GV.CB: (CENTER, CENTER, CENTER, OFF_END),
            },
            # These are the tracking lines that will not go through the center.
            OFF_CENTER: {
                GV.LR: (START, ABOVE_CENTER, END, ABOVE_CENTER),
                GV.RL: (END, BELOW_CENTER, START, BELOW_CENTER),
                GV.TB: (RIGHT_TO_CENTER, START, RIGHT_TO_CENTER, END),
                GV.BT: (LEFT_TO_CENTER, END, LEFT_TO_CENTER, START),
                GV.BLTR: (START, CENTER, RIGHT_TO_CENTER, START),
                GV.TRBL: (RIGHT_TO_CENTER, START, START, CENTER),
                GV.BRTL: (END, CENTER, LEFT_TO_CENTER, START),
                GV.TLBR: (LEFT_TO_CENTER, START, END, CENTER),
            },
        }

        self._speed_dict = {
            GV.SLOW: 33,
            GV.NORMAL: 100,
            GV.FAST: 300,
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
            #           that guarantee both fingers on the trackpad.
            GV.HORIZONTAL: (CENTER, CENTER),
            GV.VERTICAL: (END, CENTER),
            GV.DIAGONAL: (CENTER, END),

            # location parameters for one_finger_click and two_finger_click
            None: (CENTER, CENTER),
        }

        self._build_robot_script_paths()


        # If the robot is actually connected, we should calibrate the Z height
        # for this device immediately.  This generates a file that over-rides
        # the values found in the device description
            self._calibrate_z(should_calibrate)

    def _calibrate_z(self, should_calibrate):
        """ Clear any old calibration files and possibly generate a new one """
        if os.path.isfile(CALIBRATION_FILE):
            os.remove(CALIBRATION_FILE)

        if self._is_robot_action_mode() and should_calibrate:
            calibrate_script = os.path.join(self._robot_script_dir,
                                            'calibrate_z.py')
            calibrate_cmd = 'python %s %s' % (calibrate_script, self._board)
            common_util.simple_system(calibrate_cmd)

            if not os.path.isfile(CALIBRATION_FILE):
                self._raise_error('Z calibration failed')

    def _is_robot_action_mode(self):
        """Is it in robot action mode?

        In the robot action mode, it actually invokes the robot control script.
        """
        return self._mode in [MODE.ROBOT, MODE.ROBOT_INT]

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

    def _get_basic_tracking_or_swipe(self, gesture):
        """Determine whether the gesture is a basic tracking or a swipe."""
        if SWIPE in gesture:
            return SWIPE
        else:
            return BASIC

    def _get_tap_or_click(self, gesture):
        """Determine whether the gesture is a tap or a click."""
        if TAP in gesture:
            return TAP
        elif CLICK in gesture:
            return CLICK
        else:
            return None

    def _get_num_taps(self, gesture):
        """Determine the number of times to tap."""
        matches = re.match('[^0-9]*([0-9]*)[^0-9]*', gesture)
        return matches.group(1) if matches else None

    def _get_control_command_line(self, robot_script, gesture, variation):
        """Get robot control command for gestures using robot line script."""
        # Determine whether this is a basic tracking gesture or a swipe.
        basic_tracking_or_swipe = self._get_basic_tracking_or_swipe(gesture)
        if not basic_tracking_or_swipe:
            msg = 'Cannot determine whether "%s" is basic tracking or swipe.'
            self._raise_error(msg % gesture)

        # Determine which line dictionary to use.
        is_finger_crossing = (gesture == conf.FINGER_CROSSING)
        dict_choice = OFF_CENTER if is_finger_crossing else THROUGH_CENTER
        line_dict = self._line_dict[dict_choice]

        line = speed = None
        for element in variation:
            if element in GV.GESTURE_DIRECTIONS:
                line = line_dict[element]
            elif element in GV.GESTURE_SPEED:
                speed = self._speed_dict[element]

        # The speed is assigned in the one_finger_tracking gesture.
        # For the swipe gesture, no speed is specified in test_conf.
        # Hence, need to assign FAST to the speed of the swipe gesture.
        if basic_tracking_or_swipe == SWIPE:
            speed = self._speed_dict[GV.FAST]

        if line is None or speed is None:
            msg = 'Cannot derive the line/speed parameters from %s %s.'
            self._raise_error(msg % (gesture, variation))

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
                location_str = ' '.join(map(str, location))
                break

        if location is None:
            msg = 'Cannot derive the location parameters from %s %s.'
            self._raise_error(msg % (gesture, variation))

        tap_or_click = self._get_tap_or_click(gesture)
        if not tap_or_click:
            msg = 'Cannot determine whether "%s" is a tap or a click.'
            self._raise_error(msg % gesture)

        para = (robot_script, self._board, location_str, tap_or_click)
        control_cmd = 'python %s %s %s %s' % para
        return control_cmd

    def _get_control_command_rapid_taps(self, robot_script, gesture, variation):
        """Get robot control command for the rapid tap gestures."""
        location = None
        for element in variation:
            location = self._location_dict.get(element)
            if location:
                location_str = ' '.join(map(str, location))
                break

        if location is None:
            msg = 'Cannot determine the location parameters from %s %s.'
            self._raise_error(msg % (gesture, variation))

        num_taps = self._get_num_taps(gesture)
        if not num_taps:
            msg = 'Cannot determine the number of taps to do from %s.'
            self._raise_error(msg % gesture)

        para = (robot_script, self._board, location_str, num_taps)
        control_cmd = 'python %s %s %s %s' % para
        return control_cmd


    def _get_control_command_replay(self, robot_script, gesture, variation):
        """Get robot control command for replaying the existent gestures."""
        control_cmd = 'python %s' % robot_script
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
        # If the (gesture, variation) is the same as the previous one, use
        # the replay script (run_program.py)
        if self._gesture_variation == (gesture, variation):
            script_method = self._get_control_command_replay
        else:
            # Check if there exists a method to derive the robot script command
            # for this gesture.
            script_method = self._method_of_control_command_dict.get(gesture)
            if not script_method:
                self._raise_error('Cannot find "%s" gesture in '
                                  '_method_of_control_command_dict.' % gesture)
            self._gesture_variation = (gesture, variation)

        robot_script = self._robot_script_dict.get(script_method)
        if not robot_script:
            msg = 'Cannot find "%s" method in _robot_script_dict.'
            self._raise_error(msg % script_method)

        return script_method(robot_script, gesture, variation)

    def _execute_control_command(self, control_cmd):
        """Execute a control command."""
        print 'Executing: "%s"' % control_cmd
        if self._is_robot_action_mode():
            common_util.simple_system(control_cmd)

    def control(self, gesture, variation):
        """Have the robot perform the gesture variation."""
        if not isinstance(variation, tuple):
            variation = (variation,)
        try:
            print gesture.name, variation
            control_cmd = self._get_control_command(gesture.name, variation)
            self._execute_control_command(control_cmd)
        except RobotWrapperError as e:
            print gesture.name, variation
            print 'RobotWrapperError: %s' % str(e)
