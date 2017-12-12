# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import shutil
import time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome


class autoupdate_StartOOBEUpdate(test.test):
    """Starts a forced update at OOBE.

    Chrome OS will restart when the update is complete so this test will just
    start the update. The rest of the processing will be done in a server
    side test.
    """
    version = 1
    _LANGUAGE_SELECT = 'language-select'
    _CUSTOM_LSB_RELEASE = '/mnt/stateful_partition/etc/lsb-release'


    def setup(self):
        utils.run('rm %s' % self._CUSTOM_LSB_RELEASE, ignore_status=True)


    def cleanup(self):
        logging.info('Update engine log saved to results dir.')
        shutil.copy('/var/log/update_engine.log', self.resultsdir)


    def _is_oobe_ready(self):
        """Check that Chrome OS OOBE is ready."""
        return (self._chrome.browser.oobe and
                self._chrome.browser.oobe.EvaluateJavaScript(
                    "var select = document.getElementById('%s');"
                    "select && select.children.length >= 2" %
                    self._LANGUAGE_SELECT))


    def _clear_local_state(self):
        """Clear local state so OOBE is reset."""
        utils.run('rm /home/chronos/Local\ State', ignore_status=True)


    def _setup_custom_lsb_release(self, update_url):
        """Create a custom lsb-release file.

        In order to tell OOBE to ping a different update server than the
        default we need to create our own lsb-release. We will include a
        deserver update URL.

        @param update_url: The update url to use.

        """
        utils.run('mkdir /mnt/stateful_partition/etc', ignore_status=True)
        utils.run('touch %s' % self._CUSTOM_LSB_RELEASE)
        utils.run('echo CHROMEOS_RELEASE_VERSION=0.0.0.0 >> %s' %
                  self._CUSTOM_LSB_RELEASE)
        utils.run('echo CHROMEOS_AUSERVER=%s >> %s' %
                  (update_url, self._CUSTOM_LSB_RELEASE))


    def _step_through_oobe_screens(self):
        """Walk through the OOBE to the update check screen."""
        utils.poll_for_condition(
            self._is_oobe_ready, timeout=30, sleep_interval=1,
            exception=error.TestFail('OOBE not ready'))

        # TODO(dhaddock): Replace with single call when crbug.com/790015 fixed.
        lets_go = "$('oobe-welcome-md').$.welcomeScreen.$.welcomeNextButton" \
                  ".click()"
        self._oobe.EvaluateJavaScript(lets_go)
        time.sleep(3)
        next_button = "$('oobe-welcome-md').$.networkSelectionScreen" \
                      ".querySelector('oobe-next-button').click()"
        self._oobe.EvaluateJavaScript(next_button)
        time.sleep(3)
        self._oobe.EvaluateJavaScript("$('accept-button').disabled = false")
        self._oobe.EvaluateJavaScript("$('accept-button').click()")
        time.sleep(3)


    def _check_update_screen_visible(self):
        """Make sure we are currently on the update scren at OOBE."""
        result = self._oobe.EvaluateJavaScript("Oobe.getInstance("
                                               ").currentScreen.id")
        if result != 'update':
            raise error.TestFail('We were not on the update screen when we '
                                 'expected to be. Check logs in resultsdir.')


    def run_once(self, image_url):
        utils.run('restart update-engine')

        self._clear_local_state()
        self._setup_custom_lsb_release(image_url)

        # Start chrome instance to interact with OOBE.
        self._chrome = chrome.Chrome(auto_login=False)
        self._oobe = self._chrome.browser.oobe

        self._step_through_oobe_screens()
        self._check_update_screen_visible()

        update_started = False
        while not update_started:
            status = utils.run('update_engine_client --status',
                               ignore_timeout=True).stdout
            status = status.splitlines()
            logging.info(status)
            time.sleep(1)
            if 'UPDATE_STATUS_DOWNLOADING' in status[2]:
                update_started = True
            elif 'UPDATE_STATUS_CHECKING_FOR_UPDATE' in status[2]:
                continue
            elif 'UPDATE_STATUS_UPDATE_AVAILABLE' in status[2]:
                continue
            else:
                raise error.TestFail('update_engine had an unexpected status: '
                                     '%s. Check logs and update_engine.log in '
                                     'the results dir.' % status[2])
