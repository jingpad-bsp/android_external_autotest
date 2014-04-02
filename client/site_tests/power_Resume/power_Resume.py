# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.cros import power_suspend


class power_Resume(test.test):
    version = 1
    preserve_srcdir = True

    def initialize(self):
        self._suspender = power_suspend.Suspender(self.resultsdir,
                throw=True, device_times=True)


    def run_once(self, max_devs_returned=10, seconds=3):
        # TODO: Reduce duration to 0 once stress tests have proven it to be safe
        (results, device_times) = self._suspender.suspend(seconds)

        # return as keyvals the slowest n devices
        slowest_devs = sorted(
            device_times,
            key=device_times.get,
            reverse=True)[:max_devs_returned]
        for dev in slowest_devs:
            results[dev] = device_times[dev]

        results['seconds_3G_disconnect'] = self._suspender.disconnect_3G_time

        self.write_perf_keyval(results)
