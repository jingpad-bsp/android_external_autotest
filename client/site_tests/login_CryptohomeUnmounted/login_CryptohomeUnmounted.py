# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, time
from autotest_lib.client.bin import site_cryptohome, site_login, test
from autotest_lib.client.common_lib import error

class login_CryptohomeUnmounted(test.test):
    version = 1

    def setup(self):
        site_login.setup_autox(self)

    def run_once(self, script = 'autox_script.json', is_control = False):
        logged_in = site_login.logged_in()

        # Require that the cryptohome is mounted before testing that
        # logging out will unmount it.  This requires logging in.
        if not logged_in:
            site_login.attempt_login(self, script)

        if not site_cryptohome.is_mounted(allow_fail = is_control):
            raise error.TestFail('Expected cryptohome to be mounted')

        site_login.attempt_logout()

        # allow the command to fail, so we can handle the error here
        if site_cryptohome.is_mounted(allow_fail = True):
            raise error.TestFail('Expected cryptohome NOT to be mounted')

        # If we started logged in, reset the state.
        if logged_in:
            site_login.attempt_login(self, script)
