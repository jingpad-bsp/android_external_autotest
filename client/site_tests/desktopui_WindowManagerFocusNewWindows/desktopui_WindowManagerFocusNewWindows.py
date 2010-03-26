# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, time
from autotest_lib.client.bin import site_login, test
from autotest_lib.client.common_lib import error

class desktopui_WindowManagerFocusNewWindows(test.test):
    version = 1

    def setup(self):
        site_login.setup_autox(self)

    def __check_active_window(self, id, info):
        """Check that a particular window is active.

        Args:
            id: int window ID
            info: AutoX.WindowInfo object corresponding to 'id'

        Raises:
            error.TestFail: if a condition timed out
        """
        try:
            self.autox.await_condition(
                lambda: info.is_focused,
                desc='Waiting for window 0x%x to be focused' % id)
            self.autox.await_condition(
                lambda: self.autox.get_active_window_property() == id,
                desc='Waiting for _NET_ACTIVE_WINDOW to contain 0x%x' % id)

            # get_geometry() returns a tuple, so we need to construct a tuple to
            # compare against it.
            fullscreen_dimensions = \
                tuple([0, 0] + list(self.autox.get_screen_size()))
            self.autox.await_condition(
                lambda: info.get_geometry() == fullscreen_dimensions,
                desc='Waiting for window 0x%x to fill the screen' % id)

            self.autox.await_condition(
                lambda: self.autox.get_top_window_id_at_point(200, 200) == id,
                desc='Waiting for window 0x%x to be on top' % id)

        except self.autox.ConditionTimeoutError as exception:
            raise error.TestFail(
                'Timed out on condition: %s' % exception.__str__())

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
        self.autox = autox.AutoX()

        # Create a window and check that we switch to it.
        win = self.autox.create_and_map_window(
            width=200, height=200, title='test')
        info = self.autox.get_window_info(win.id)
        self.__check_active_window(win.id, info)

        # Create a second window.
        win2 = self.autox.create_and_map_window(
            width=200, height=200, title='test 2')
        info2 = self.autox.get_window_info(win2.id)
        self.__check_active_window(win2.id, info2)

        # Cycle backwards to the first window.
        self.autox.send_hotkey('Alt-Shift-Tab')
        self.__check_active_window(win.id, info)

        # Cycle forwards to the second window.
        self.autox.send_hotkey('Alt-Tab')
        self.__check_active_window(win2.id, info2)

        # Now destroy the second window and check that the WM goes back
        # to the first window.
        win2.destroy()
        self.__check_active_window(win.id, info)
