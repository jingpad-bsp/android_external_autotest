# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.cros import cros_ui_test, login

class desktopui_WindowManagerHotkeys(cros_ui_test.UITest):
    version = 1


    def initialize(self, creds = '$default'):
        cros_ui_test.UITest.initialize(self, creds)


    def run_once(self):
        # Make sure that we don't have the initial browser window popping up in
        # the middle of the test.
        login.wait_for_initial_chrome_window()

        ax = self.get_autox()

        # Start a terminal and wait for it to get the focus.
        orig_active_win_xid = ax.get_active_window_property()
        ax.send_hotkey('Ctrl-Alt-t')
        ax.await_condition(
            lambda: ax.get_active_window_property() != orig_active_win_xid,
            desc='Waiting for terminal to become active window')
