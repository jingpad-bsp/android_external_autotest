# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server import test
from autotest_lib.server.cros import telemetry_runner


class telemetry_ScrollingBenchmark(test.test):
    """Run the telemetry scrolling benchmark."""
    version = 1


    def run_once(self, host=None):
        """Run the telemetry scrolling benchmark.

        @param host: host we are running telemetry on.
        """
        telemetry = telemetry_runner.TelemetryRunner(host)
        telemetry.run_telemetry_benchmark('scrolling_benchmark',
                                          'tough_scrolling_cases.json',
                                          keyval_writer=self)
