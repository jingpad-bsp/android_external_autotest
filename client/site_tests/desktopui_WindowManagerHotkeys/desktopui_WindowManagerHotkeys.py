# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, random, time
from autotest_lib.client.bin import site_login, test
from autotest_lib.client.common_lib import error

class desktopui_WindowManagerHotkeys(test.test):
    version = 1

    def setup(self):
        site_login.setup_autox(self)

    # TODO: This would be useful for other tests; put it somewhere else.
    def __poll_for_condition(
            self, condition, desc='', timeout=10, sleep_interval=0.1):
        """Poll until a condition becomes true.

        condition: function taking no args and returning bool
        desc: str description of the condition
        timeout: maximum number of seconds to wait
        sleep_interval: time to sleep between polls

        Raises:
            error.TestFail: if the condition doesn't become true
        """
        start_time = time.time()
        while True:
            if condition():
                return
            if time.time() + sleep_interval - start_time > timeout:
                raise error.TestFail(
                    'Timed out waiting for condition: %s' % desc)
            time.sleep(sleep_interval)

    def run_once(self):
        import autox

        # TODO: This should be abstracted out.
        if not site_login.logged_in():
            if not site_login.attempt_login(self, 'autox_script.json'):
                raise error.TestError('Could not log in')
            if not site_login.wait_for_window_manager():
                raise error.TestError('Window manager didn\'t start')
            # TODO: This is awful.  We need someone (Chrome, the WM, etc.) to
            # announce when login is "done" -- that is, the initial Chrome
            # window isn't going to pop onscreen in the middle of the test.
            # For now, we just sleep a really long time.
            time.sleep(20)

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
        self.__poll_for_condition(
            lambda: os.access(temp_filename, os.F_OK),
            desc='Waiting for %s to be created from terminal' % temp_filename)
        os.remove(temp_filename)

        # Press the Print Screen key and check that a screenshot is written.
        screenshot_filename = '/home/chronos/user/screenshot.png'
        if os.access(screenshot_filename, os.F_OK):
            os.remove(screenshot_filename)
        ax.send_hotkey('Print')
        self.__poll_for_condition(
            lambda: os.access(screenshot_filename, os.F_OK),
            desc='Waiting for screenshot at %s' % screenshot_filename)
        os.remove(screenshot_filename)
