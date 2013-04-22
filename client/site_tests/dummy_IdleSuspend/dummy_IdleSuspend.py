# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, time

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, power_suspend, power_utils


class dummy_IdleSuspend(cros_ui_test.UITest):
    """
    This is not a complete test. It is a dummy test that must be run in parallel
    with power_SuspendStress(method='idle') to control powerd idle values and
    perform a login.
    """
    version = 1

    _IDLE_TIMINGS = {
        'disable_idle_suspend': 0,
        'ignore_external_policy': 1,
        'unplugged_dim_ms': 4000,
        'unplugged_off_ms': 6000,
        'unplugged_suspend_ms': 8000,
        'plugged_dim_ms': 4000,
        'plugged_off_ms': 6000,
        'plugged_suspend_ms': 8000,
    }

    # Don't wait longer than this to start... if power_SuspendStress died before
    # creating the HWCLOCK_FILE, we might otherwise wait forever
    _TEST_START_TIMEOUT = 70

    def initialize(self, creds='$default'):
        # It's important to log in with a real user. If logged in as
        # guest, powerd will shut down instead of suspending.
        super(dummy_IdleSuspend, self).initialize(creds=creds)


    def run_once(self):
        # We just idle while power_SuspendStress does all the work. Existance of
        # the HWCLOCK_FILE tells us when it starts and when it's done.
        for _ in xrange(self._TEST_START_TIMEOUT):
            time.sleep(1)
            if os.path.exists(power_suspend.Suspender.HWCLOCK_FILE):
                break
        else:
            raise error.TestError("Parallel test failed to create Suspender.")

        # These must not be enabled too soon, or the system may suspend before a
        # wakeup is scheduled. They must not be disabled too late either...
        power_prefs = power_utils.PowerPrefChanger(self._IDLE_TIMINGS)

        while os.path.exists(power_suspend.Suspender.HWCLOCK_FILE):
            time.sleep(1)

        power_prefs.finalize()
