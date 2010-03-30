# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, random, time
from autotest_lib.client.bin import site_ui_test, site_utils, test
from autotest_lib.client.common_lib import error

class desktopui_WindowManagerHotkeys(site_ui_test.UITest):
    version = 1

    def run_once(self):
        import autox

        # TODO: Set these in a single, standard place for all tests.
        os.environ['DISPLAY'] = ':0'
        os.environ['XAUTHORITY'] = '/home/chronos/.Xauthority'
        ax = autox.AutoX()

        # Start a terminal and wait for it to get the focus.
        # TODO: This is a bit of a hack.  To watch for the terminal getting
        # the focus, we create a new window, wait for it to get the focus,
        # and then launch the terminal and wait for our window to lose the
        # focus (AutoX isn't notified about focus events on the terminal
        # window itself).  It's maybe cleaner to add a method to AutoX to
        # get the currently-focused window and then just poll that after
        # starting the terminal until it changes.
        win = ax.create_and_map_window()
        info = ax.get_window_info(win.id)
        ax.await_condition(
            lambda: info.is_focused,
            desc='Waiting for window to get focus')
        ax.send_hotkey('Ctrl-Alt-t')
        ax.await_condition(
            lambda: not info.is_focused,
            desc='Waiting for window to lose focus')

        # Type in it to create a file in /tmp and exit.
        temp_filename = '/tmp/desktopup_WindowManagerHotkeys_%d' % time.time()
        ax.send_text('touch %s\n' % temp_filename)
        ax.send_text('exit\n')
        site_utils.poll_for_condition(
            lambda: os.access(temp_filename, os.F_OK),
            error.TestFail(
                'Waiting for %s to be created from terminal' % temp_filename))
        os.remove(temp_filename)

        # Press the Print Screen key and check that a screenshot is written.
        screenshot_filename = '/home/chronos/user/screenshot.png'
        if os.access(screenshot_filename, os.F_OK):
            os.remove(screenshot_filename)
        ax.send_hotkey('Print')
        site_utils.poll_for_condition(
            lambda: os.access(screenshot_filename, os.F_OK),
            error.TestFail(
                'Waiting for screenshot at %s' % screenshot_filename))
        os.remove(screenshot_filename)
