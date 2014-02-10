# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib.cros import chrome


class desktopui_SimpleLogin(test.test):
    """Login and wait until exit flag file is seen."""
    version = 1


    def run_once(self):
        """Entrance point for test."""
        terminate_path = '/tmp/simple_login_exit'
        if os.path.isfile(terminate_path):
            os.remove(terminate_path)

        with chrome.Chrome():
            while True:
                time.sleep(1)
                if os.path.isfile(terminate_path):
                    logging.info('Exit flag detected; exiting.')
                    return
