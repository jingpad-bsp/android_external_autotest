# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, time
from autotest_lib.client.bin import site_cryptohome, site_ui_test
from autotest_lib.client.common_lib import error

class login_CryptohomeUnmounted(site_ui_test.UITest):
    version = 1

    def run_once(self, is_control=False):
        if not site_cryptohome.is_mounted(allow_fail = is_control):
            raise error.TestFail('Expected cryptohome to be mounted')

        self.logout()

        # allow the command to fail, so we can handle the error here
        if site_cryptohome.is_mounted(allow_fail = True):
            raise error.TestFail('Expected cryptohome NOT to be mounted')
