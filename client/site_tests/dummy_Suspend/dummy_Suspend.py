# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.cros import sys_power


class dummy_Suspend(test.test):
    """Dummy test to suspend the DUT. Use case is to called from other test."""

    version = 1

    def run_once(self, suspend_seconds=15, delay_seconds=0):
        """
        @param suspend_seconds: Number of seconds to suspend the DUT.
        @param delay_seconds: Number of seconds wait before suspending the DUT.
        """

        sys_power.do_suspend(suspend_seconds, delay_seconds)
