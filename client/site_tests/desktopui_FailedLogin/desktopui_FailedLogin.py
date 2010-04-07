# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, time
from autotest_lib.client.bin import site_ui_test, site_login
from autotest_lib.client.common_lib import error

class desktopui_FailedLogin(site_ui_test.UITest):
    version = 1

    auto_login = False

    def run_once(self):
        # TODO(cmasone): find better way to determine login has failed.
        try:
            self.login('bogus@bogus.gmail.com', 'bogus')
        except site_login.TimeoutError:
            pass
        else:
            raise error.TestFail('Should not have logged in')
