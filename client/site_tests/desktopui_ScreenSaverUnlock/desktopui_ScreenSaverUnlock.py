# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
from autotest_lib.client.bin import site_ui_test, site_utils
from autotest_lib.client.common_lib import error

class desktopui_ScreenSaverUnlock(site_ui_test.UITest):
    version = 1


    def run_once(self, is_control=False):
        self.wait_for_screensaver()
        self.xsystem('xscreensaver-command -lock')

        site_utils.poll_for_condition(
            lambda: self.is_screensaver_locked(),
            desc='screensaver lock')

        ax = self.get_autox()

        # Send a key and wait for the screensaver to wakeup and
        # present the login dialog.
        # TODO: a less brittle way to do this would be nice
        ax.send_hotkey('Return')
        time.sleep(2)

        if is_control:
            # send an incorrect password
            ax.send_text('_boguspassword_')
            ax.send_hotkey('Return')

            # verify that the screen unlock attempt failed
            try:
                site_utils.poll_for_condition(
                    lambda: self.is_screensaver_unlocked(),
                    desc='screensaver unlock')
            except error.TestError:
                pass
            else:
                raise error.TestFail('screen saver unlocked with bogus password.')
        else:
            # send the correct password
            ax.send_text(self.password)
            ax.send_hotkey('Return')

            # wait for screen to unlock
            site_utils.poll_for_condition(
                lambda: self.is_screensaver_unlocked(),
                desc='screensaver unlock')
