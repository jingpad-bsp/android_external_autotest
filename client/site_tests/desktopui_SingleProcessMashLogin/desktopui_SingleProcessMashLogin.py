# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib.cros import chrome


class desktopui_SingleProcessMashLogin(test.test):
    """Verifies chrome starts up and logs in correctly."""
    version = 1


    def run_once(self):
        """Entry point of this test."""

        # GPU info collection via devtools SystemInfo.getInfo does not work
        # under mash due to differences in how the GPU process is configured
        # with mus hosting viz. http://crbug.com/669965
        browser_args = ['--enable-features=SingleProcessMash',
                        '--gpu-no-complete-info-collection']

        logging.info('Testing Chrome with SingleProcessMash startup.')
        with chrome.Chrome(auto_login=False, extra_browser_args=browser_args):
            logging.info('Chrome startup with SingleProcessMash succeeded.')

        logging.info('Testing Chrome with SingleProcessMash login.')
        with chrome.Chrome(extra_browser_args=browser_args):
            logging.info('Chrome login with SingleProcessMash succeeded.')
