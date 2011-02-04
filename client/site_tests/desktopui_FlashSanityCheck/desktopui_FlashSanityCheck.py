# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, time
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants, cros_logging, cros_ui
from autotest_lib.client.cros import cros_ui_test, login


class desktopui_FlashSanityCheck(cros_ui_test.UITest):
    version = 2


    def run_once(self, time_to_wait=25):
        self._log_reader = cros_logging.LogReader()
        self._log_reader.set_start_by_current()

        # Make sure that we don't have the initial browser window popping up in
        # the middle of the test.
        login.wait_for_initial_chrome_window()
        # TODO(sosa): Check in flash video that is a solid test.
        session = cros_ui.ChromeSession(
            '--user-data-dir=%s %s' % (constants.CRYPTOHOME_MOUNT_PT,
                                       'http://www.youtube.com'),
            clean_state=False, suid=True)
        # Wait some time till the webpage got fully loaded.
        time.sleep(time_to_wait)
        session.close()

        # Any better pattern matching?
        if self._log_reader.can_find(' Received crash notification for '):
            raise error.TestFail('Browser crashed during test.')
