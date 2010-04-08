# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, utils, time
from autotest_lib.client.bin import chromeos_constants
from autotest_lib.client.bin import site_cryptohome, site_login, test
from autotest_lib.client.common_lib import error

class login_CryptohomeMounted(test.test):
    version = 1

    # TODO: figure the right fix for missing setup_autox
    # def setup(self):
    #     site_login.setup_autox(self)

    def run_once(self, script='autox_script.json', is_control=False):
        # Make sure that we're logged out initially -- this test is run
        # multiple times, and we don't want to reuse the previous instance's
        # session.
        if site_login.logged_in():
            site_login.attempt_logout()

        # Test account information embedded into json file.
        site_login.attempt_login(self, script)

        if (not is_control and
            not site_cryptohome.is_mounted(allow_fail=is_control)):
            raise error.TestFail('CryptohomeIsMounted should return %s' %
                                 (not is_control))

        site_login.attempt_logout()
