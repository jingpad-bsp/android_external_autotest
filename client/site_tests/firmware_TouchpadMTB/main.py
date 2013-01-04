# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module sets up the system for the touchpad firmware test suite."""


# Include the paths for running pyauto to show test result html file.
import sys
sys.path.append('/usr/local/autotest/cros')
pyautolib = '/usr/local/autotest/deps/pyauto_dep/test_src/chrome/test/pyautolib'
sys.path.append(pyautolib)
import httpd
import pyauto

import getopt
import logging
import os
import sys

import firmware_utils
import firmware_window
import keyboard_device
import mtb
import test_conf as conf
import test_flow
import touch_device

from firmware_constants import MODE, OPTIONS
from report_html import ReportHtml


def setup_http_data_dir():
    """Set up the default http data dir for pyauto test.

    When creating a test http server, it checks the default http data dir
    no matter whether it is actually used. If the http data dir does not exist,
    it throws out the testserver_base.OptionError.
    """
    autotest_dir = '/usr/local/autotest'
    pyauto_test_dir = 'deps/pyauto_dep/test_src'
    data_dir = 'chrome/test/data'
    http_data_dir = os.path.join(autotest_dir, pyauto_test_dir, data_dir)
    if not os.path.isdir(http_data_dir):
        try:
            os.makedirs(http_data_dir)
            msg = 'http data directory created successfully: %s'
            logging.info(msg % http_data_dir)
        except os.error, e:
            logging.error('Making the default http data dir: %s.' % e)
            exit(-1)


class DummyTest(pyauto.PyUITest):
    """This is a dummpy test class derived from PyUITest to use pyauto tool."""
    def test_navigate_to_url(self):
        """Navigate to the html test result file using pyauto."""
        testServer = httpd.HTTPListener(8000, conf.docroot)
        testServer.run()
        # Note that the report_html_name is passed from firmware_TouchpadMTB
        # to DummyTest as an environment variable.
        # It is not passed as a global variable in this module because pyauto
        # seems to create its own global scope.
        report_html_name = os.environ[conf.ENVIRONMENT_REPORT_HTML_NAME]
        if report_html_name:
            base_url = os.path.basename(report_html_name)
            url = os.path.join('http://localhost:8000', base_url)
            self.NavigateToURL(url)
            msg = 'Chrome has navigated to the specified url: %s'
            logging.info(msg % os.path.join(conf.docroot, base_url))
        testServer.stop()


class firmware_TouchpadMTB:
    """Set up the system for touchpad firmware tests."""

    def __init__(self, options):
        # Create the touchpad device.
        self.touchpad = touch_device.TouchpadDevice()
        self._check_device(self.touchpad)

        # Create the keyboard device.
        self.keyboard = keyboard_device.KeyboardDevice()
        self._check_device(self.keyboard)

        # Get the MTB parser.
        self.parser = mtb.MtbParser()

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

        # Create the HTML report object and the output object to print messages
        # on the window and to print the results in the report.
        firmware_version = self.touchpad.get_firmware_version()
        mode = options[OPTIONS.MODE]
        self.log_dir = firmware_utils.create_log_dir(firmware_version, mode)
        self._create_report_name(mode)
        self.report_html = ReportHtml(self.report_html_name,
                                      self.screen_size,
                                      self.touchpad_window_size,
                                      conf.score_colors)
        self.output = firmware_utils.Output(self.log_dir,
                                            self.report_name,
                                            self.win, self.report_html)

        # Get the test_flow object which will guide through the gesture list.
        self.test_flow = test_flow.TestFlow(self.touchpad_window_geometry,
                                            self.touchpad,
                                            self.keyboard,
                                            self.win,
                                            self.parser,
                                            self.output,
                                            options=options)

        # Register some callback functions for firmware window
        self.win.register_callback('expose_event',
                                   self.test_flow.init_gesture_setup_callback)

        # Register a callback function to watch keyboard input events.
        # This is required because the set_input_focus function of a window
        # is flaky maybe due to problems of the window manager.
        # Hence, we handle the keyboard input at a lower level.
        self.win.register_io_add_watch(self.test_flow.user_choice_callback,
                                       self.keyboard.system_device)

        # Stop power management so that the screen does not dim during tests
        firmware_utils.stop_power_management()

    def _check_device(self, device):
        """Check if a device has been created successfully."""
        if device.device_node is None:
            logging.error('Cannot find device_node.')
            exit(-1)

    def _create_report_name(self, mode):
        """Create the report names for both plain-text and html files.

        A typical html file name looks like:
            touchpad_firmware_report-lumpy-fw_11.25-20121016_080924.html
        """
        firmware_str = 'fw_' + self.touchpad.get_firmware_version()
        board = firmware_utils.get_board()
        curr_time = firmware_utils.get_current_time_str()
        fname = conf.filename.sep.join([conf.report_basename,
                                        board,
                                        firmware_str,
                                        mode,
                                        curr_time])
        self.report_name = os.path.join(self.log_dir, fname)
        self.report_html_name = self.report_name + conf.html_ext
        # Pass the report_html_name to DummyTest as an environment variable.
        os.environ[conf.ENVIRONMENT_REPORT_HTML_NAME] = self.report_html_name

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
        firmware_utils.start_power_management()
        setup_http_data_dir()
        pyauto.Main()


def _usage():
    """Print the usage of this program."""
    print 'Usage: $ %s [options]\n' % sys.argv[0]
    print 'options:'
    print '  -h, --%s: show this help' % OPTIONS.HELP
    print '  -m, --%s: gesture playing mode' % OPTIONS.MODE
    print '            could be one of the following options'
    print '            COMPLETE: all gestures including those in ' \
                                'both MANUAL mode and ROBOT mode'
    print '            MANUAL: all gestures - gestures in ROBOT mode'
    print '            ROBOT: using robot to perform gestures automatically'
    print '            ROBOT_INT: using robot with finger interaction'
    print '            ROBOT_SIM: robot simulation, for developer only'
    print '  -s, --%s: Use one variation per gesture' % OPTIONS.SIMPLIFIED
    print


def _parsing_error(msg):
    """Print the usage and exit when encountering parsing error."""
    print 'Error: %s' % msg
    _usage()
    sys.exit(1)


def _parse_options():
    """Parse the options.

    Note that the options are specified with environment variable OPTIONS,
    because pyauto seems not compatible with command line options.
    """
    # Initialize and get the environment OPTIONS
    options = {OPTIONS.MODE: MODE.MANUAL, OPTIONS.SIMPLIFIED: False}
    options_str = os.environ.get('OPTIONS')
    if not options_str:
        return options

    options_list = options_str.split()
    try:
        short_opt = 'hm:s'
        long_opt = [OPTIONS.HELP, OPTIONS.MODE, OPTIONS.SIMPLIFIED]
        opts, args = getopt.getopt(options_list, short_opt, long_opt)
    except getopt.GetoptError, err:
        _parsing_error(str(err))

    for opt, arg in opts:
        if opt in ('-h', '--%s' % OPTIONS.HELP):
            _usage()
            sys.exit(1)
        elif opt in ('-m', '--%s' % OPTIONS.MODE):
            if arg in MODE.GESTURE_PLAY_MODE:
                options[OPTIONS.MODE] = arg
            else:
                print 'Warning: -m should be one of %s' % MODE.GESTURE_PLAY_MODE
        elif opt in ('-s', '--%s' % OPTIONS.SIMPLIFIED):
            options[OPTIONS.SIMPLIFIED] = True
        else:
            msg = 'This option "%s" is not supported.' % opt
            _parsing_error(opt)

    print 'Note: the %s mode is used.' % options[OPTIONS.MODE]
    return options


if __name__ == '__main__':
    options = _parse_options()
    fw = firmware_TouchpadMTB(options)
    fw.main()
