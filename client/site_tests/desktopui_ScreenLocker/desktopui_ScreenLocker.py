# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test


class desktopui_ScreenLocker(cros_ui_test.UITest):
    version = 1


    def initialize(self, creds='$default', **dargs):
        cros_ui_test.UITest.initialize(self, creds, **dargs)


    def is_screen_locked(self):
        return self.pyauto.GetLoginInfo()['is_screen_locked']


    def run_once(self):
        self.pyauto.LockScreen()

        if not self.is_screen_locked():
            error.TestFail('screenlocker not locked')

        # send an incorrect password
        error_msg = self.pyauto.UnlockScreen('_boguspassword_')
        # verify that the screen unlock attempt failed
        if not error_msg or not self.is_screen_locked():
            raise error.TestFail('unlocked with bogus password: %s' % error_msg)

        # send the correct password
        error_msg = self.pyauto.UnlockScreen(self.password)
        if error_msg or self.is_screen_locked():
            raise error.TestFail('could not unlock screensaver: %s' % error_msg)
