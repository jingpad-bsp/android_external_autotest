# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants, cros_ui_test, login

class login_OwnershipTaken(cros_ui_test.UITest):
    version = 1

    def initialize(self, creds='$default'):
        self.auto_login = False  # Will log in manually later.
        super(login_OwnershipTaken, self).initialize(creds,
                                                     is_creating_owner=True)
        if os.access(constants.OWNER_KEY_FILE, os.F_OK):
            raise error.TestFail("Ownership already taken!")
        self.login(self.username, self.password)

    def run_once(self):
        login.wait_for_ownership()
