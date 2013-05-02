# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

#pylint: disable-msg=C0111

import os
from autotest_lib.client.cros import constants
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, cryptohome, login

TEST_USER = 'cryptohome_test@chromium.org'
TEST_PASS = 'testme'
TEST_FILE = os.path.join(constants.CRYPTOHOME_MOUNT_PT, 'hello')


class login_CryptohomeMounted(cros_ui_test.UITest):
    version = 1

    def initialize(self, creds='$default'):
        try:
            super(login_CryptohomeMounted, self).initialize(creds)
        except Exception as err:
            raise error.TestFailRetry(err)


    def run_once(self):
        try:
            login.wait_for_cryptohome()
            self.logout()
            cryptohome.remove_vault(TEST_USER)
            cryptohome.mount_vault(TEST_USER, TEST_PASS, create=True)
            open(TEST_FILE, 'w').close()
            cryptohome.unmount_vault(TEST_USER)
            self.login()
            login.wait_for_cryptohome()
            self.assert_(not os.path.exists(TEST_FILE))
        #TODO: Make this more fine-grained. See crbug.com/225542
        except Exception as err:
            raise error.TestFailRetry(err)
