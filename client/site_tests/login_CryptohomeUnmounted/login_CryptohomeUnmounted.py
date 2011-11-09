# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, cryptohome, login

class login_CryptohomeUnmounted(cros_ui_test.UITest):
    version = 2

    def initialize(self, creds='$default'):
        super(login_CryptohomeUnmounted, self).initialize(creds)


    def run_once(self):
        if not cryptohome.is_mounted(allow_fail=False):
            raise error.TestFail('Expected cryptohome to be mounted')

        self.logout()

        # allow the command to fail, so we can handle the error here
        if cryptohome.is_mounted(allow_fail=True):
            raise error.TestFail('Expected cryptohome NOT to be mounted')
