# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
from autotest_lib.client.bin import site_ui_test

class login_LoginSuccess(site_ui_test.UITest):
    version = 1


    def run_once(self):
        time.sleep(5) # Local login is so fast, it needs to be slowed down.
