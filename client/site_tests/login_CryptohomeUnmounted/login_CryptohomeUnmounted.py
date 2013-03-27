# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

#pylint: disable-msg=C0111

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, cryptohome

class login_CryptohomeUnmounted(cros_ui_test.UITest):
    version = 2

    def initialize(self, creds='$default'):
        super(login_CryptohomeUnmounted, self).initialize(creds)


    def run_once(self):
        try:
            if not cryptohome.is_vault_mounted(user=self.username,
                                               allow_fail=False):
                raise error.TestFail('Expected to find a mounted vault.')

            self.logout()

            # Allow the command to fail, so we can handle the error here.
            if cryptohome.is_vault_mounted(user=self.username, allow_fail=True):
                raise error.TestFail('Expected to NOT find a mounted vault.')
        #TODO: Make this more fine-grained. See crbug.com/225542
        except Exception as err:
            raise error.TestFailRetry(err)
