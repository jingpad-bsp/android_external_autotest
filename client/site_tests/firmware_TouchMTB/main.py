# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module sets up the system for the touch device firmware test suite."""

import getopt
import logging
import os
import sys

import cros_gs
import firmware_utils
import firmware_window
import keyboard_device
import mtb
import test_conf as conf
import test_flow
import touch_device
import validators

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
            logging.info(msg, http_data_dir)
        except os.error, e:
            logging.error('Making the default http data dir: %s.', e)
            exit(-1)


# Include the paths and import required modules for running pyauto if
# pyauto has been installed so that the test result file could be displayed
# on Chrome automatically when all tests are finished.
pyautolib = '/usr/local/autotest/deps/pyauto_dep/test_src/chrome/test/pyautolib'
is_pyauto_installed = os.path.isdir(pyautolib)
if is_pyauto_installed:
    sys.path.append('/usr/local/autotest/cros')
    sys.path.append(pyautolib)
    import httpd
    import pyauto

    class DummyTest(pyauto.PyUITest):
        """This is a dummpy test class derived from PyUITest to use pyauto tool.
        """
        def test_navigate_to_url(self):
            """Navigate to the html test result file using pyauto."""
            testServer = httpd.HTTPListener(8000, conf.docroot)
            testServer.run()
            # Note that the report_html_name is passed from firmware_TouchMTB
            # to DummyTest as an environment variable.
            # It is not passed as a global variable in this module because
            # pyauto seems to create its own global scope.
            report_html_name = os.environ[conf.ENVIRONMENT_REPORT_HTML_NAME]
            if report_html_name:
                base_url = os.path.basename(report_html_name)
                url = os.path.join('http://localhost:8000', base_url)
                self.NavigateToURL(url)
                msg = 'Chrome has navigated to the specified url: %s'
                logging.info(msg, os.path.join(conf.docroot, base_url))
            testServer.stop()


class firmware_TouchMTB:
    """Set up the system for touch device firmware tests."""

    def __init__(self, options):
        # Get the board name
        self.board = firmware_utils.get_board()

        # Set up gsutil package
        self.gs = cros_gs.get_or_install_gsutil(self.board)

        # Create the touch device
        # If you are going to be testing a touchscreen, set it here
        self.touch_device = touch_device.TouchDevice(
            is_touchscreen=options[OPTIONS.TOUCHSCREEN])
        self._check_device(self.touch_device)
        validators.init_base_validator(self.touch_device)

        # Create the keyboard device.
        self.keyboard = keyboard_device.KeyboardDevice()
        self._check_device(self.keyboard)

        # Get the MTB parser.
        self.parser = mtb.MtbParser()

        # Get the chrome browser.
        self.chrome = firmware_utils.SimpleX('aura')

        # Create a simple gtk window.
        self._get_screen_size()
        self._get_touch_device_window_geometry()
        self._get_prompt_frame_geometry()
        self._get_result_frame_geometry()
        self.win = firmware_window.FirmwareWindow(
                size=self.screen_size,
                prompt_size=self.prompt_frame_size,
                image_size=self.touch_device_window_size,
                result_size=self.result_frame_size)

        # Create the HTML report object and the output object to print messages
        # on the window and to print the results in the report.
        firmware_version = self.touch_device.get_firmware_version()
        mode = options[OPTIONS.MODE]
        if options[OPTIONS.RESUME]:
            self.log_dir = options[OPTIONS.RESUME]
        elif options[OPTIONS.REPLAY]:
            self.log_dir = options[OPTIONS.REPLAY]
        else:
            self.log_dir = firmware_utils.create_log_dir(firmware_version, mode)
        self._create_report_name(mode)
        self.report_html = ReportHtml(self.report_html_name,
                                      self.screen_size,
                                      self.touch_device_window_size,
                                      conf.score_colors)
        self.output = firmware_utils.Output(self.log_dir,
                                            self.report_name,
                                            self.win, self.report_html)

        # Get the test_flow object which will guide through the gesture list.
        self.test_flow = test_flow.TestFlow(self.touch_device_window_geometry,
                                            self.touch_device,
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
            touch_firmware_report-lumpy-fw_11.25-20121016_080924.html
        """
        firmware_str = 'fw_' + self.touch_device.get_firmware_version()
        curr_time = firmware_utils.get_current_time_str()
        fname = conf.filename.sep.join([conf.report_basename,
                                        self.board,
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

    def _get_touch_device_window_geometry(self):
        """Get the preferred window geometry to display mtplot."""
        display_ratio = 0.7
        self.touch_device_window_geometry = \
                self.touch_device.get_display_geometry(
                self.screen_size, display_ratio)
        self.touch_device_window_size = self.touch_device_window_geometry[0:2]

    def _get_prompt_frame_geometry(self):
        """Get the display geometry of the prompt frame."""
        (_, wint_height, _, _) = self.touch_device_window_geometry
        screen_width, screen_height = self.chrome.get_screen_size()
        win_x = 0
        win_y = 0
        win_width = screen_width
        win_height = screen_height - wint_height
        self.winp_geometry = (win_x, win_y, win_width, win_height)
        self.prompt_frame_size = (win_width, win_height)

    def _get_result_frame_geometry(self):
        """Get the display geometry of the test result frame."""
        (wint_width, wint_height, _, _) = self.touch_device_window_geometry
        screen_width, _ = self.chrome.get_screen_size()
        win_width = screen_width - wint_width
        win_height = wint_height
        self.result_frame_size = (win_width, win_height)

    def main(self):
        """A helper to enter gtk main loop."""
        upload_choice = fw.win.main()
        if upload_choice:
            print 'Uploading %s to %s ...' % (self.log_dir, self.gs.bucket)
            self.gs.upload(self.log_dir)
        firmware_utils.start_power_management()
        if is_pyauto_installed:
            setup_http_data_dir()
            pyauto.Main()


def _usage_and_exit():
    """Print the usage of this program."""
    print 'Usage: $ DISPLAY=:0 [OPTIONS="options"] python %s\n' % sys.argv[0]
    print 'options:'
    print '  -h, --%s' % OPTIONS.HELP
    print '        show this help'
    print '  -i, --%s iterations' % OPTIONS.ITERATIONS
    print '        specify the number of iterations'
    print '  -m, --%s mode' % OPTIONS.MODE
    print '        specify the gesture playing mode'
    print '        mode could be one of the following options'
    print '            complete: all gestures including those in ' \
                                'both manual mode and robot mode'
    print '            manual: all gestures minus gestures in robot mode'
    print '            robot: using robot to perform gestures automatically'
    print '            robot_int: using robot with finger interaction'
    print '            robot_sim: robot simulation, for developer only'
    print '  --%s log_dir' % OPTIONS.REPLAY
    print '        Replay the gesture files and get the test results.'
    print '        log_dir is a log sub-directory in %s' % conf.log_root_dir
    print '  --%s log_dir' % OPTIONS.RESUME
    print '        Resume recording the gestures files in the log_dir.'
    print '        log_dir is a log sub-directory in %s' % conf.log_root_dir
    print '  -s, --%s' % OPTIONS.SIMPLIFIED
    print '        Use one variation per gesture'
    print '  -t, --%s' % OPTIONS.TOUCHSCREEN
    print '        Use the touchscreen instead of a touchpad'
    print
    print 'Example:'
    print '  # Use the robot to perform 3 iterations of the robot gestures.'
    print '  $ DISPLAY=:0 OPTIONS="-m robot_sim -i 3" python main.py\n'
    print '  # Perform 1 iteration of the manual gestures.'
    print '  $ DISPLAY=:0 OPTIONS="-m manual" python main.py\n'
    print '  # Perform 1 iteration of all manual and robot gestures.'
    print '  $ DISPLAY=:0 OPTIONS="-m complete" python main.py\n'
    print '  # Replay the gesture files in the latest log directory.'
    print '  $ DISPLAY=:0 OPTIONS="--replay latest" python main.py\n'
    example_log_dir = '20130226_040802-fw_1.2-manual'
    print '  # Replay the gesture files in %s/%s' % (conf.log_root_dir,
                                                     example_log_dir)
    print '  $ DISPLAY=:0 OPTIONS="--replay %s" python main.py\n' % \
            example_log_dir

    print '  # Resume recording the gestures in the latest log directory.'
    print '  $ DISPLAY=:0 OPTIONS="--resume latest" python main.py\n'
    print '  # Resume recording the gestures in %s/%s.' % (conf.log_root_dir,
                                                           example_log_dir)
    print '  $ DISPLAY=:0 OPTIONS="--resume %s" python main.py\n' % \
            example_log_dir
    sys.exit(1)


def _parsing_error(msg):
    """Print the usage and exit when encountering parsing error."""
    print 'Error: %s' % msg
    _usage_and_exit()


def _parse_options():
    """Parse the options.

    Note that the options are specified with environment variable OPTIONS,
    because pyauto seems not compatible with command line options.
    """
    # Set the default values of options.
    options = {OPTIONS.ITERATIONS: 1,
               OPTIONS.MODE: MODE.MANUAL,
               OPTIONS.REPLAY: None,
               OPTIONS.RESUME: None,
               OPTIONS.SIMPLIFIED: False,
               OPTIONS.TOUCHSCREEN: False}

    # Get the environment OPTIONS
    options_str = os.environ.get('OPTIONS')
    if not options_str:
        return options

    options_list = options_str.split()
    try:
        short_opt = 'hi:m:st'
        long_opt = [OPTIONS.HELP,
                    OPTIONS.ITERATIONS + '=',
                    OPTIONS.MODE + '=',
                    OPTIONS.REPLAY + '=',
                    OPTIONS.RESUME + '=',
                    OPTIONS.SIMPLIFIED,
                    OPTIONS.TOUCHSCREEN]
        opts, args = getopt.getopt(options_list, short_opt, long_opt)
    except getopt.GetoptError, err:
        _parsing_error(str(err))

    for opt, arg in opts:
        if opt in ('-h', '--%s' % OPTIONS.HELP):
            _usage_and_exit()
        elif opt in ('-i', '--%s' % OPTIONS.ITERATIONS):
            if arg.isdigit():
                options[OPTIONS.ITERATIONS] = int(arg)
            else:
                _usage_and_exit()
        elif opt in ('-m', '--%s' % OPTIONS.MODE):
            arg = arg.lower()
            if arg in MODE.GESTURE_PLAY_MODE:
                options[OPTIONS.MODE] = arg
            else:
                print 'Warning: -m should be one of %s' % MODE.GESTURE_PLAY_MODE
        elif opt in ('--%s' % OPTIONS.REPLAY, '--%s' % OPTIONS.RESUME):
            log_dir = os.path.join(conf.log_root_dir, arg)
            if os.path.isdir(log_dir):
                # opt could be either '--replay' or '--resume'.
                # We would like to strip off the '-' on the left hand side.
                options[opt.lstrip('-')] = log_dir
            else:
                print 'Error: the log directory "%s" does not exist.' % log_dir
                _usage_and_exit()
        elif opt in ('-s', '--%s' % OPTIONS.SIMPLIFIED):
            options[OPTIONS.SIMPLIFIED] = True
        elif opt in ('-t', '--%s' % OPTIONS.TOUCHSCREEN):
            options[OPTIONS.TOUCHSCREEN] = True
        else:
            msg = 'This option "%s" is not supported.' % opt
            _parsing_error(opt)

    print 'Note: the %s mode is used.' % options[OPTIONS.MODE]
    return options


if __name__ == '__main__':
    options = _parse_options()
    fw = firmware_TouchMTB(options)
    fw.main()
