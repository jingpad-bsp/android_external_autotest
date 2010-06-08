# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
from autotest_lib.client.bin import site_login, site_ui_test
from autotest_lib.client.common_lib import error

class login_RemoteLogin(site_ui_test.UITest):
    version = 1


    def start_authserver(self):
        pass


    def ensure_login_complete(self):
        if not site_login.logged_in():
            raise error.TestFail("Did not log in.")


    def run_once(self):
        pass


    def stop_authserver(self):
        pass
