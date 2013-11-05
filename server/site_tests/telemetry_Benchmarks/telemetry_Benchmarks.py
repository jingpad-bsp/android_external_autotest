# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from autotest_lib.server import test
from autotest_lib.server.cros import telemetry_runner


class telemetry_Benchmarks(test.test):
    """Run a telemetry benchmark."""
    version = 1


    def run_once(self, host=None, benchmark=None):
        """Run a telemetry benchmark.

        @param host: host we are running telemetry on.
        @param benchmark: benchmark we want to run.
        """
        telemetry = telemetry_runner.TelemetryRunner(host)
        telemetry.run_telemetry_benchmark(benchmark, keyval_writer=self)
