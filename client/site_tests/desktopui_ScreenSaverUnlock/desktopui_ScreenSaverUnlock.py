# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
from autotest_lib.client.bin import site_ui_test, site_utils


class desktopui_ScreenSaverUnlock(site_ui_test.UITest):
    version = 1


    def run_once(self):
        self.wait_for_screensaver()
        self.xsystem('xscreensaver-command -lock')

        site_utils.poll_for_condition(
            lambda: self.is_screensaver_locked(),
            desc='screensaver lock')

        ax = self.get_autox()
        ax.send_hotkey('Return')
        # wait for the screensaver to wakeup and present the login dialog
        # TODO: a less brittle way to do this would be nice
        time.sleep(2)
        ax.send_text(self.password)
        ax.send_hotkey('Return')

        # wait for screen to unlock
        site_utils.poll_for_condition(
            lambda: self.is_screensaver_unlocked(),
            desc='screensaver unlock')
