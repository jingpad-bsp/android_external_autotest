# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, time
from autotest_lib.client.bin import chromeos_utils, test
from autotest_lib.client.common_lib import error

class desktopui_DoLogin(test.test):
    version = 1

    def setup(self):
        chromeos_utils.setup_autox(self)

    def run_once(self):
        logged_in = chromeos_utils.logged_in()

        # Can't test login while logged in, so logout.
        if logged_in:
            if not chromeos_utils.attempt_logout():
                raise error.TestFail('Could not terminate existing session')
            if not chromeos_utils.wait_for_login_manager():
                raise error.TestFail("Login manager didn't come back")

        # Test account information embedded into json file.
        if not chromeos_utils.attempt_login(self, 'autox_script.json'):
            raise error.TestFail('Could not login')

        # If we started logged out, log back out.
        if not logged_in:
            chromeos_utils.attempt_logout()
