# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import cryptohome, login

TEST_USER = 'cryptohome_test@chromium.org'
TEST_PASS = 'testme'

class login_CryptohomeMountedTelemetry(test.test):
    """Verify the cryptohome is mounted after login."""
    version = 1


    def run_once(self):
        """Verifies cryptohome is mounted after login (uses Telemetry login)."""
        try:
            with chrome.login() as _:
                login.wait_for_cryptohome(chrome.LOGIN_USER)
            cryptohome.remove_vault(chrome.LOGIN_USER)

            cryptohome.mount_vault(TEST_USER, TEST_PASS, create=True)
            test_file = os.path.join(cryptohome.user_path(TEST_USER), 'hello')
            open(test_file, 'w').close()
            cryptohome.unmount_vault(TEST_USER)

            with chrome.login() as _:
                login.wait_for_cryptohome(chrome.LOGIN_USER)
                self.assert_(not os.path.exists(test_file))
        # TODO(dennisjeffrey): Make this more fine-grained.
        # See crbug.com/225542.
        except Exception as err:
            raise error.TestFailRetry(repr(err))
