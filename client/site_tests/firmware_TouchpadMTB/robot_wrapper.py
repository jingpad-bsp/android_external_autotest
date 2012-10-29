# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A wrapper for robot manipulation."""

import os

import common_util
import test_conf as conf

from firmware_constants import GV


class RobotWrapper:
    """A class to wrap and manipulate the robot library."""

    def __init__(self, board):
        self.board = board
        self.robot_action_dict = {
                GV.LR: (0.0, 0.5, 1.0, 0.5),
                GV.RL: (1.0, 0.5, 0.0, 0.5),
                GV.TB: (0.5, 0.0, 0.5, 1.0),
                GV.BT: (0.5, 1.0, 0.5, 0.0),
                GV.BLTR: (0.1, 0.9, 0.9, 0.1),
                GV.TRBL: (0.9, 0.1, 0.1, 0.9),
                GV.BRTL: (0.9, 0.9, 0.1, 0.1),
                GV.TLBR: (0.1, 0.1, 0.9, 0.9),
                GV.SLOW: 33,
                GV.NORMAL: 100,
        }
        self.robot_script_dir = self._get_robot_script_dir()

    def _get_robot_script_dir(self):
        """Get the directory of the robot control scripts."""
        cmd = 'find %s -name %s' % (conf.robot_lib_path, conf.python_package)
        path = common_util.simple_system_output(cmd)
        if path:
            robot_script_dir = os.path.join(path, conf.gestures_sub_path)
            if os.path.isdir(robot_script_dir):
                return robot_script_dir
        return None

    def control(self, gesture, variation):
        """Have the robot perform the gesture variation."""
        if not self.robot_script_dir:
            script_path = os.path.join(conf.robot_lib_path, conf.python_package,
                                       conf.gestures_sub_path)
            msg = 'Error: cannot find robot script directory in "%s".'
            print msg % script_path
            return

        direction = speed = None
        for element in variation:
            if element in GV.GESTURE_DIRECTIONS:
                direction = self.robot_action_dict[element]
            elif element in GV.GESTURE_SPEED:
                speed = self.robot_action_dict[element]

        # TODO(josephsih): use 'line.py' only at this time.
        # Need to define a dictionary to associate gestures with scripts.
        robot_script = os.path.join(self.robot_script_dir, 'line.py')
        if not os.path.isfile(robot_script):
            print 'Error: cannot find robot control script: %s' % robot_script
            return

        start_x, start_y, end_x, end_y = direction
        para = (robot_script, self.board, start_x, start_y, end_x, end_y, speed)
        control_cmd = 'python %s %s %f %f %f %f %f' % para
        print gesture.name, variation
        print 'Executing: "%s"' % control_cmd
        common_util.simple_system(control_cmd)
