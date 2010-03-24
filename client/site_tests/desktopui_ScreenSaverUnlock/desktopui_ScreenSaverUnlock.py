# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time, utils
from autotest_lib.client.bin import site_login, test
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import chromeos_constants

class desktopui_ScreenSaverUnlock(test.test):
    version = 1

    def system_as(self, cmd, user='chronos'):
        utils.system('su %s -c \'%s\'' % (user, cmd))

    def setup(self):
        site_login.setup_autox(self)

    def run_once(self):
        if site_login.logged_in():
            if not site_login.attempt_logout():
                raise error.TestFail('Could not terminate existing session')

        if not site_login.attempt_login(self, 'autox_script.json'):
            raise error.TestFail('Could not login')

        # first sleep to let the login finish and start xscreensaver
        time.sleep(10)
        self.system_as('DISPLAY=:0.0 xscreensaver-command -lock')

        # some sleep to let the screen lock
        time.sleep(5)
        self.system_as('DISPLAY=:0.0 xscreensaver-command -time | ' +
                       'grep -q locked')

        time.sleep(10)
        if not site_login.attempt_login(self, 'autox_unlock.json'):
            raise error.TestFail('Could not unlock screensaver')

        # wait for screen to unlock
        time.sleep(5)
        self.system_as('DISPLAY=:0.0 xscreensaver-command -time | ' +
                       'grep -q non-blanked')
