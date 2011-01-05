# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, login

class login_RemoteLogin(cros_ui_test.UITest):
    version = 1


    def initialize(self, creds = '$default'):
        cros_ui_test.UITest.initialize(self, creds)


    def start_authserver(self):
        pass


    def ensure_login_complete(self):
        if not login.logged_in():
            raise error.TestFail("Did not log in.")


    def run_once(self):
        pass


    def stop_authserver(self):
        pass
