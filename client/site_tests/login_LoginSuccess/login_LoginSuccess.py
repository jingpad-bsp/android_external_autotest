# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
from autotest_lib.client.bin import site_ui_test

class login_LoginSuccess(site_ui_test.UITest):
    version = 1


    def run_once(self):
        pass


    def cleanup(self):
        super(login_LoginSuccess, self).cleanup()
        self.write_perf_keyval(self.get_auth_endpoint_misses())
