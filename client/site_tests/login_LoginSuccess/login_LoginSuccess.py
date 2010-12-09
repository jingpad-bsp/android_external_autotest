# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
from autotest_lib.client.cros import ui_test

class login_LoginSuccess(ui_test.UITest):
    version = 1


    def ensure_login_complete(self):
        """Wait for login to complete, including cookie fetching."""
        self._authServer.wait_for_client_login()
        self._authServer.wait_for_issue_token()
        self._authServer.wait_for_test_over()


    def run_once(self):
        pass


    def cleanup(self):
        super(login_LoginSuccess, self).cleanup()
        self.write_perf_keyval(self.get_auth_endpoint_misses())
