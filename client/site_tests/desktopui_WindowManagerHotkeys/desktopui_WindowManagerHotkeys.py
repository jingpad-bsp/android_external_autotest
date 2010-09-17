# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, random, re, shutil, time
from autotest_lib.client.bin import site_ui_test, site_utils, test, utils
from autotest_lib.client.common_lib import error

class desktopui_WindowManagerHotkeys(site_ui_test.UITest):
    version = 1

    def run_once(self):
        ax = self.get_autox()

        # Start a terminal and wait for it to get the focus.
        orig_active_win_xid = ax.get_active_window_property()
        ax.send_hotkey('Ctrl-Alt-t')
        ax.await_condition(
            lambda: ax.get_active_window_property() != orig_active_win_xid,
            desc='Waiting for terminal to become active window')

        # Press the Print Screen key and check that a screenshot is written.
        screenshot_dir = '/home/chronos/user/Downloads/Screenshots'
        shutil.rmtree(screenshot_dir, ignore_errors=True)
        ax.send_hotkey('Print')
        site_utils.poll_for_condition(
            lambda: os.access(screenshot_dir, os.F_OK) and \
                    os.listdir(screenshot_dir),
            error.TestFail(
                'Waiting for screenshot in %s' % screenshot_dir))
        shutil.rmtree(screenshot_dir, ignore_errors=True)
