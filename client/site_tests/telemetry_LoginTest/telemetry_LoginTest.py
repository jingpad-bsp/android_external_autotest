# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome

class telemetry_LoginTest(test.test):
    """This is a client side Telemetry Login Test."""
    version = 1


    def run_once(self):
        """
        This test imports telemetry, restarts and connects to chrome, navigates
        the login flow and checks to ensure that the login process is
        completed.
        """
        with chrome.logged_in_browser():
            # By creating a browser and using 'with' any code in this section
            # is wrapped by a login/logout.
            if not os.path.exists('/var/run/state/logged-in'):
                raise error.TestFail('Failed to log into the system.')
