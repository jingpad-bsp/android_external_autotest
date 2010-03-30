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
        # Can't test login while logged in, so logout.
        if site_login.logged_in():
            site_login.attempt_logout()

        # Test account information embedded into json file.
        # TODO(cmasone): find better way to determine login has failed.
        try:
            site_login.attempt_login(self, script)
        except site_login.TimeoutError:
            pass
        else:
            raise error.TestFail('Should not have logged in')

        # Re-set to a good state
        site_login.nuke_login_manager()
