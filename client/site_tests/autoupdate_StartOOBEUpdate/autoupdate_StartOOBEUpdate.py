# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import shutil

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
    _CUSTOM_LSB_RELEASE = '/mnt/stateful_partition/etc/lsb-release'


    def setup(self):
        utils.run('rm %s' % self._CUSTOM_LSB_RELEASE, ignore_status=True)


    def cleanup(self):
        logging.info('Update engine log saved to results dir.')
        shutil.copy('/var/log/update_engine.log', self.resultsdir)


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


    def _skip_to_oobe_update_screen(self):
        """Skips to the OOBE update check screen."""
        self._oobe.WaitForJavaScriptCondition("typeof Oobe == 'function' && "
                                              "Oobe.readyForTesting",
                                              timeout=30)
        self._oobe.ExecuteJavaScript('Oobe.skipToUpdateForTesting()')


    def _is_update_started(self):
        """Checks if the update has started."""
        status = utils.run('update_engine_client --status',
                           ignore_timeout=True).stdout
        status = status.splitlines()
        logging.info(status)
        return 'UPDATE_STATUS_DOWNLOADING' in status[2]


    def run_once(self, image_url):
        utils.run('restart update-engine')

        self._setup_custom_lsb_release(image_url)

        # Start chrome instance to interact with OOBE.
        self._chrome = chrome.Chrome(auto_login=False)
        self._oobe = self._chrome.browser.oobe

        self._skip_to_oobe_update_screen()
        utils.poll_for_condition(self._is_update_started,
                                 error.TestFail('Update did not start.'),
                                 timeout=30)

