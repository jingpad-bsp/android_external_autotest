# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Some utility classes and functions."""

import os
import re
import sys
import time

import common_util

# Include some constants
execfile('firmware_constants.py', globals())


def get_display_name():
    """Return the display name."""
    return ':0'


def get_tests_path():
    """Get the path for unit tests."""
    return os.path.join(os.getcwd(), 'tests')


def get_tests_data_path():
    """Get the data path for unit tests."""
    return os.path.join(get_tests_path(), 'data')


def get_current_time_str():
    """Get the string of current time."""
    time_format = '%Y%m%d_%H%M%S'
    return time.strftime(time_format, time.gmtime())


def get_board():
    """Get board of the Chromebook machine."""
    with open('/etc/lsb-release') as lsb:
        context = lsb.read()
    board = 'unknown_board'
    if context is not None:
        for line in context.splitlines():
            if line.startswith('CHROMEOS_RELEASE_BOARD'):
                board_str = line.split('=')[1]
                if '-' in board_str:
                    board = board_str.split('-')[1]
                elif '_' in board_str:
                    board = board_str.split('_')[1]
                else:
                    board = board_str
                # Some boards, e.g. alex, may have board name as alex32
                board = re.search('(\D+)\d*', board, re.I).group(1)
                break
    return board


def create_log_dir():
    """Create a directory to save the report and device event files."""
    log_root_dir = '/var/tmp/touchpad_firmware_test'
    log_dir = os.path.join(log_root_dir, get_current_time_str())
    try:
        os.makedirs(log_dir)
    except OSError, e:
        print 'Error in create the directory (%s): %s' % (log_dir, e)
        sys.exit(-1)
    return log_dir


class Gesture:
    """A class defines the structure of Gesture."""
    # define the default timeout (in milli-seconds) when performing a gesture.
    # A gesture is considered done when finger is lifted for this time interval.
    TIMEOUT = int(1000/80*10)

    def __init__(self, name=None, variations=None, prompt=None, subprompt=None,
                 validators=None, timeout=TIMEOUT):
        self.name = name
        self.variations = variations
        self.prompt = prompt
        self.subprompt = subprompt
        self.validators = validators
        self.timeout = timeout


class Output:
    """A class to handle outputs to the window and to the report."""
    def __init__(self, log_dir, report_name, win):
        self.log_dir = log_dir
        self.report_name = report_name
        self.report = open(report_name, 'w')
        self.win = win
        self.prefix_space = ' ' * 4

    def __del__(self):
        self.stop()

    def stop(self):
        """Close the report file and print it on stdout."""
        self.report.close()
        with open(self.report_name) as f:
            for line in f.read().splitlines():
                print line
        report_msg = '\n*** This test report is saved in the file: %s\n'
        print report_msg % self.report_name

    def get_prefix_space(self):
        """Get the prefix space when printing the report."""
        return self.prefix_space

    def print_report_line(self, msg):
        """Print the line with proper indentation."""
        self.report.write(self.prefix_space + str(msg) + os.linesep)

    def print_window(self, msg):
        """Print the message to the result window."""
        if type(msg) is list:
            msg = os.linesep.join(msg)
        self.win.set_result(msg)

    def print_report(self, msg):
        """Print the message to the report."""
        if type(msg) is list:
            for line in msg:
                self.print_report_line(line)
        else:
            self.print_report_line(msg)

    def print_all(self, msg):
        """Print the message to both report and to the window."""
        self.print_window(msg)
        self.print_report(msg)


class SimpleX:
    """A simple class provides some simple X methods and properties."""

    def __init__(self, win_name='aura'):
        import Xlib
        import Xlib.display
        self.Xlib = Xlib
        self.Xlib.display = Xlib.display

        self.disp = self._get_display()
        self._get_screen()
        self._get_window(win_name)

    def _get_display(self):
        """Get the display object."""
        return self.Xlib.display.Display(get_display_name())

    def _get_screen(self):
        """Get the screen instance."""
        self.screen = self.disp.screen()

    def _get_window(self, win_name):
        """Get the window with the specified name."""
        wins = self.screen.root.query_tree().children
        for win in wins:
            name = win.get_wm_name()
            if name and win_name in name:
                self.win = win
                break
        else:
            self.win = None
            print 'Error: No window is named as "%s".' % win_name

    def _get_focus_info(self):
        """Get the input focus information."""
        return self.disp.get_input_focus()

    def set_input_focus(self):
        """Set the input focus to the window id."""
        if self.win:
            self.disp.set_input_focus(self.win.id,
                                      self.Xlib.X.RevertToParent,
                                      self.Xlib.X.CurrentTime)
            self._get_focus_info()

    def get_screen_size(self):
        """Get the screen size in pixels."""
        return (self.screen.width_in_pixels, self.screen.height_in_pixels)

    def get_screen_size_in_mms(self):
        """Get the screen size in milli-meters."""
        return (self.screen.width_in_mms, self.screen.height_in_mss)

    def get_DPMM(self):
        """Get Dots per Milli-meter."""
        return (1.0 * self.screen.width_in_pixels / self.screen.width_in_mms,
                1.0 * self.screen.height_in_pixels / self.screen.height_in_mms)

    def _recover_input_focus(self):
        """Set the input focus back to the original settings."""
        self.disp.set_input_focus(self.Xlib.X.PointerRoot,
                                  self.Xlib.X.RevertToParent,
                                  self.Xlib.X.CurrentTime)
        self._get_focus_info()

    def __del__(self):
        self._recover_input_focus()


class ScreenShot:
    """Handle screen shot."""

    def __init__(self, geometry_str):
        self.geometry_str = geometry_str
        environment_str = 'DISPLAY=:0.0 XAUTHORITY=/home/chronos/.Xauthority '
        dump_util = '/usr/local/bin/import -quality 20'
        self.dump_window_format = ' '.join([environment_str, dump_util,
                                           '-window %s %s.png'])
        self.dump_root_format = ' '.join([environment_str, dump_util,
                                         '-window root -crop %s %s.png'])
        self.get_id_cmd = 'DISPLAY=:0 xwininfo -root -tree'

    def dump_window(self, filename):
        """Dump the screenshot of a window to the specified file name."""
        win_id = self._get_win_id()
        if win_id:
            dump_cmd = self.dump_window_format % (win_id, filename)
            common_util.simple_system(dump_cmd)
        else:
            print 'Warning: cannot get the window id.'

    def dump_root(self, filename):
        """Dump the screenshot of root to the specified file name."""
        dump_cmd = self.dump_root_format % (self.geometry_str, filename)
        common_util.simple_system(dump_cmd)

    def _get_win_id(self):
        """Get the window ID based on the characteristic string."""
        result = common_util.simple_system_output(self.get_id_cmd)
        for line in result.splitlines():
            if self.geometry_str in line:
                return line.split()[0].strip()
        return None
