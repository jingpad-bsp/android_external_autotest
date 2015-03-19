# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.cros import sys_power

class power_MemorySuspend(test.test):
    """Suspend the system via memory_suspend_test."""

    version = 1

    def initialize(self):
        utils.system('stop ui', ignore_status=True)


    def run_once(self, num_suspends=1):
        for _ in range(num_suspends):
            sys_power.memory_suspend(10)


    def cleanup(self):
        utils.system('start ui')
