# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time, utils
from autotest_lib.client.bin import site_login, site_ui_test, test
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import chromeos_constants

class desktopui_ScreenSaverUnlock(site_ui_test.UITest):
    version = 1

    def system_as(self, cmd, user='chronos'):
        utils.system('su %s -c \'%s\'' % (user, cmd))

    def run_once(self):
        site_login.wait_for_screensaver()
        self.system_as('DISPLAY=:0.0 xscreensaver-command -lock')

        # some sleep to let the screen lock
        # TODO: Sleeping is unreliable and slow.  Do something better to
        # wait for the screen to be locked.
        time.sleep(5)
        self.system_as('DISPLAY=:0.0 xscreensaver-command -time | ' +
                       'grep -q locked')

        time.sleep(10)
        site_login.attempt_login(self, 'autox_unlock.json')

        # wait for screen to unlock
        time.sleep(5)
        self.system_as('DISPLAY=:0.0 xscreensaver-command -time | ' +
                       'grep -q non-blanked')
