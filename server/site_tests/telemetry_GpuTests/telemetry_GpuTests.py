# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.cros.graphics import graphics_utils
from autotest_lib.server import test
from autotest_lib.server.cros import telemetry_runner


class telemetry_GpuTests(test.test):
    """Run a Chrome OS GPU telemetry test."""
    version = 1

    GSC = None

    def initialize(self):
        self.GSC = graphics_utils.GraphicsStateChecker()

    def cleanup(self):
        if self.GSC:
            self.GSC.finalize()

    def run_once(self, host=None, test=None):
        """Run a GPU telemetry test.

        @param host: host we are running telemetry on.
        @param test: telemetry test we want to run.
        """
        telemetry = telemetry_runner.TelemetryRunner(host)
        result = telemetry.run_gpu_test(test)
        logging.debug('Telemetry completed with a status of: %s with output:'
                      ' %s', result.status, result.output)
