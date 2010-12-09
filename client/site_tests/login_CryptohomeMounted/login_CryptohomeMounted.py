# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
from autotest_lib.client.bin import site_cryptohome, site_login
from autotest_lib.client.cros import constants as chromeos_constants
from autotest_lib.client.cros import ui_test

TEST_USER = 'cryptohome_test@chromium.org'
TEST_PASS = 'testme'
TEST_FILE = os.path.join(chromeos_constants.CRYPTOHOME_MOUNT_PT, 'hello')


class login_CryptohomeMounted(ui_test.UITest):
    version = 1

    def run_once(self):
        site_login.wait_for_cryptohome()
        site_login.attempt_logout()
        site_cryptohome.remove_vault(TEST_USER)
        site_cryptohome.mount_vault(TEST_USER, TEST_PASS, create=True)
        open(TEST_FILE, 'w').close()
        self.login()
        site_login.wait_for_cryptohome()
        self.assert_(not os.path.exists(TEST_FILE))
