# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
from autotest_lib.client.cros import constants as chromeos_constants
from autotest_lib.client.cros import cros_ui_test, cryptohome, login

TEST_USER = 'cryptohome_test@chromium.org'
TEST_PASS = 'testme'
TEST_FILE = os.path.join(chromeos_constants.CRYPTOHOME_MOUNT_PT, 'hello')


class login_CryptohomeMounted(cros_ui_test.UITest):
    version = 1

    def initialize(self, creds='$default'):
        super(login_CryptohomeMounted, self).initialize(creds)


    def run_once(self):
        login.wait_for_cryptohome()
        login.attempt_logout()
        cryptohome.remove_vault(TEST_USER)
        cryptohome.mount_vault(TEST_USER, TEST_PASS, create=True)
        open(TEST_FILE, 'w').close()
        self.login()
        login.wait_for_cryptohome()
        self.assert_(not os.path.exists(TEST_FILE))
