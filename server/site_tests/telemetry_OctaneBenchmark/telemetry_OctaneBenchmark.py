# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server import test
from autotest_lib.server.cros import telemetry_runner


class telemetry_OctaneBenchmark(test.test):
    """Run the telemetry octane benchmark."""
    version = 1


    def run_once(self, host=None):
        """Run the telemetry octane benchmark.

        @param host: host we are running telemetry on.
        """
        telemetry = telemetry_runner.TelemetryRunner(host)
        telemetry.run_telemetry_benchmark('octane',
                                          'octane.json',
                                          keyval_writer=self)
