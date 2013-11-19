# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib.cros import chrome

class login_LoginSuccessTelemetry(test.test):
    """Sign in using Telemetry."""
    version = 1


    def run_once(self):
        with chrome.Chrome():
            self.job.set_state('client_success', True)