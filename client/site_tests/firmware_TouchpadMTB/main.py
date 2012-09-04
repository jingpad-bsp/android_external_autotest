# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module sets up the system for the touchpad firmware test suite."""


import logging
import os

import firmware_utils
import firmware_window
import mtb
import sys
import test_conf as conf
import test_flow
import touch_device

# Include some constants
execfile('firmware_constants.py', globals())


class firmware_TouchpadMTB:
    """Set up the system for touchpad firmware tests."""

    def __init__(self):
        # Probe touchpad device node.
        self.touchpad = touch_device.TouchpadDevice()
        if self.touchpad.device_node is None:
            logging.error('Cannot find touchpad device_node.')
            exit(-1)

        # Get the gesture list.
        self.gesture_list = conf.gesture_list

        # Get the MTB parser.
        self.parser = mtb.MTBParser()

        # Get the chrome browser.
        self.chrome = firmware_utils.SimpleX('aura')

        # Create a simple gtk window.
        self._get_screen_size()
        self._get_touchpad_window_geometry()
        self._get_prompt_frame_geometry()
        self._get_result_frame_geometry()
        self.win = firmware_window.FirmwareWindow(
                size=self.screen_size,
                prompt_size=self.prompt_frame_size,
                image_size=self.touchpad_window_size,
                result_size=self.result_frame_size)

        # Create the output object to print messages on the window and to
        # print the results in the report.
        self.log_dir = firmware_utils.create_log_dir()
        self.report_name = os.path.join(self.log_dir,
                                        'touchpad_firmware_report')
        self.output = firmware_utils.Output(self.log_dir, self.report_name,
                                            self.win)

        # Get the test_flow object which will guide through the gesture list.
        self.test_flow = test_flow.TestFlow(self.touchpad_window_geometry,
                                            self.touchpad,
                                            self.win,
                                            self.parser,
                                            self.output)

        # Register some callback functions for firmware window
        self.win.register_callback('key_press_event',
                                   self.test_flow.user_choice_callback)
        self.win.register_callback('expose_event',
                                   self.test_flow.init_gesture_setup_callback)

    def _get_screen_size(self):
        """Get the screen size."""
        self.screen_size = self.chrome.get_screen_size()

    def _get_touchpad_window_geometry(self):
        """Get the preferred window geometry to display mtplot."""
        display_ratio = 0.7
        self.touchpad_window_geometry = self.touchpad.get_display_geometry(
                self.screen_size, display_ratio)
        self.touchpad_window_size = self.touchpad_window_geometry[0:2]

    def _get_prompt_frame_geometry(self):
        """Get the display geometry of the prompt frame."""
        (_, wint_height, _, _) = self.touchpad_window_geometry
        screen_width, screen_height = self.chrome.get_screen_size()
        win_x = 0
        win_y = 0
        win_width = screen_width
        win_height = screen_height - wint_height
        self.winp_geometry = (win_x, win_y, win_width, win_height)
        self.prompt_frame_size = (win_width, win_height)

    def _get_result_frame_geometry(self):
        """Get the display geometry of the test result frame."""
        (wint_width, wint_height, _, _) = self.touchpad_window_geometry
        screen_width, _ = self.chrome.get_screen_size()
        win_width = screen_width - wint_width
        win_height = wint_height
        self.result_frame_size = (win_width, win_height)

    def main(self):
        """A helper to enter gtk main loop."""
        fw.win.main()


if __name__ == '__main__':
    fw = firmware_TouchpadMTB()
    fw.main()
