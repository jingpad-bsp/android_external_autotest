# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, time
from autotest_lib.client.bin import site_login, test
from autotest_lib.client.common_lib import error

class desktopui_FailedLogin(test.test):
    version = 1

    def setup(self):
        site_login.setup_autox(self)

    def run_once(self, script):
        logged_in = site_login.logged_in()

        # Can't test login while logged in, so logout.
        if logged_in:
            if not site_login.attempt_logout():
                raise error.TestFail('Could not terminate existing session')
            if not site_login.wait_for_login_manager():
                raise error.TestFail("Login manager didn't come back")

        # Test account information embedded into json file.
        # TODO(cmasone): find better way to determine login has failed.
        if site_login.attempt_login(self, script):
            raise error.TestFail('Should not have logged in')

        # Re-set to a good state
        site_login.nuke_login_manager()
