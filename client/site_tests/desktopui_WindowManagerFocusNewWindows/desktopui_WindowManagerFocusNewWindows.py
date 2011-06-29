# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, time
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, login

class desktopui_WindowManagerFocusNewWindows(cros_ui_test.UITest):
    version = 1


    def initialize(self, creds = '$default'):
        cros_ui_test.UITest.initialize(self, creds)


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
                lambda: self.autox.get_active_window_property() == id,
                desc='Waiting for _NET_ACTIVE_WINDOW to contain 0x%x' % id)
            self.autox.await_condition(
                lambda: info.is_focused,
                desc='Waiting for window 0x%x to be focused' % id)

        except self.autox.ConditionTimeoutError as exception:
            raise error.TestFail(
                'Timed out on condition: %s' % exception.__str__())

    def run_once(self):
        # Make sure that we don't have the initial browser window popping up in
        # the middle of the test.
        login.wait_for_initial_chrome_window()

        self.autox = self.get_autox()

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
