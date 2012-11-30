# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, random, time

from autotest_lib.client.cros import cros_ui_test, power_suspend


class power_UiResume(cros_ui_test.UITest):
    version = 1

    def initialize(self, creds='$default'):
        # It's important to log in with a real user. If logged in as
        # guest, powerd will shut down instead of suspending.
        super(power_UiResume, self).initialize(creds=creds)
        self._suspender = power_suspend.Suspender(use_dbus=True, throw=True)


    def run_once(self):
        for _ in xrange(10):
            try:
                # Some idle time before initiating suspend-to-ram
                time.sleep(random.randint(3, 7))
                results = self._suspender.suspend(random.randint(5, 11))
                break
            except power_suspend.HwClockError:
                if not power_suspend.HwClockError.is_affected(): raise
                logging.warn('Known RTC interrupt bug on this board, retrying')
        else:
            raise power_suspend.HwClockError('RTC kept failing for 10 retries')

        self.write_perf_keyval(results)
