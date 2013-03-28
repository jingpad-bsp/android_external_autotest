# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os

from telemetry.core import browser_options, browser_finder

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class telemetry_LoginTest(test.test):
    """This is a client side Telemetry Login Test."""
    version = 1


    def run_once(self):
        """
        This test imports telemetry, restarts and connects to chrome, navigates
        the login flow and checks to ensure that the login process is
        completed.
        """
        default_options = browser_options.BrowserOptions()
        default_options.browser_type = 'system'
        browser_to_create = browser_finder.FindBrowser(default_options)
        logging.debug('Browser Found: %s', browser_to_create)

        with browser_to_create.Create() as b:
            # By creating a browser and using 'with' any code in this section
            # is wrapped by a login/logout.
            if not os.path.exists('/var/run/state/logged-in'):
                raise error.TestFail('Failed to log into the system.')
