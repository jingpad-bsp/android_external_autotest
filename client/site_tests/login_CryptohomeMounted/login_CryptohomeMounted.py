# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import site_login, site_ui_test

class login_CryptohomeMounted(site_ui_test.UITest):
    version = 1

    def run_once(self, is_control=False):
        if not is_control:
            site_login.wait_for_cryptohome()
