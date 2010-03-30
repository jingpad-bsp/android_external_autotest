# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import site_login, test as bin_test
from autotest_lib.client.common_lib import error


class UITest(bin_test.test):
    """
    Tests that require the user to be logged in should subclass this test
    This script by default logs in using the default remote account, however,
    tests can override this by setting script="your_script" in the control
    file running the test
    """
    version = 1


    def setup(self):
        site_login.setup_autox(self)


    def initialize(self, script='autox_script.json'):
        # Clean up past state and assume logged out before logging in.
        if site_login.logged_in():
            site_login.attempt_logout()

        # Test account information embedded into json file.
        site_login.attempt_login(self, script)
        site_login.wait_for_initial_chrome_window()

    def cleanup(self):
        """Logs out when object is deleted"""
        site_login.attempt_logout()
