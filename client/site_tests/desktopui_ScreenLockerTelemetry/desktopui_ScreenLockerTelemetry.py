# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome


class desktopui_ScreenLockerTelemetry(test.test):
    """This is a client side test that exercises the screenlocker."""
    version = 1


    @property
    def screen_locked(self):
        """True if the screen is locked."""
        return self._chrome.login_status['isScreenLocked']


    @property
    def screenlocker_visible(self):
        """True if the screenlocker screen is visible."""
        oobe = self._chrome.browser.oobe
        return (oobe and
                oobe.EvaluateJavaScript(
                       "typeof Oobe == 'function'") and
                oobe.EvaluateJavaScript(
                       "typeof Oobe.authenticateForTesting == 'function'"))


    @property
    def error_bubble_visible(self):
        """True if the error bubble for bad password is visible."""
        return not self._chrome.browser.oobe.EvaluateJavaScript(
                "document.getElementById('bubble').hidden;")


    def attempt_unlock(self, password=''):
        """Attempt to unlock a locked screen. The correct password is the empty
           string.

        @param password: password to use to attempt the unlock.

        """
        self._chrome.browser.oobe.ExecuteJavaScript(
                "Oobe.authenticateForTesting('test@test.test', '%s');"
                % password)


    def lock_screen(self):
        """Lock the screen."""
        logging.debug('lock_screen')
        if self.screen_locked:
            raise error.TestFail('Screen already locked')
        ext = self._chrome.autotest_ext
        ext.EvaluateJavaScript('chrome.autotestPrivate.lockScreen();')
        utils.poll_for_condition(lambda: self.screenlocker_visible,
                exception=error.TestFail('Screenlock screen not visible'))
        if not self.screen_locked:
            raise error.TestFail('Screen not locked')


    def attempt_unlock_bad_password(self):
        """Attempt unlock with a bad password."""
        logging.debug('attempt_unlock_bad_password')
        if self.error_bubble_visible:
            raise error.TestFail('Error bubble prematurely visible')
        self.attempt_unlock('bad')
        utils.poll_for_condition(lambda: self.error_bubble_visible,
                exception=error.TestFail('Bad password bubble did not show'))
        if not self.screen_locked:
            raise error.TestFail('Screen unlocked with bad password')


    def unlock_screen(self):
        """Unlock the screen with the right password."""
        logging.debug('unlock_screen')
        self.attempt_unlock()
        utils.poll_for_condition(
                lambda: not self._chrome.browser.oobe_exists,
                exception=error.TestFail('Failed to unlock screen'))
        if self.screen_locked:
            raise error.TestFail('Screen should be unlocked')


    def run_once(self):
        """
        This test locks the screen, tries to unlock with a bad password,
        then unlocks with the right password.

        """
        with chrome.Chrome(autotest_ext=True) as self._chrome:
            self.lock_screen()
            self.attempt_unlock_bad_password()
            self.unlock_screen()

