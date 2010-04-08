# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, utils, time
from autotest_lib.client.bin import chromeos_constants
from autotest_lib.client.bin import site_cryptohome, site_ui_test
from autotest_lib.client.common_lib import error

class login_CryptohomeMounted(site_ui_test.UITest):
    version = 1

    def run_once(self, is_control=False):
        if (not is_control and
            not site_cryptohome.is_mounted(allow_fail=is_control)):
            raise error.TestFail('CryptohomeIsMounted should return %s' %
                                 (not is_control))
