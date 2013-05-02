# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server import test
from autotest_lib.server.cros import telemetry_runner


class telemetry_CrosTests(test.test):
    """Run a Chrome OS telemetry test."""
    version = 1


    def run_once(self, host=None, test=''):
        """Run a CrOS specific telemetry test.

        @param host: host we are running telemetry on.
        @param test: telemetry test we want to run.
        """
        telemetry = telemetry_runner.TelemetryRunner(host)
        result = telemetry.run_cros_telemetry_test(test)
        logging.debug('Telemetry completed with a status of: %s with output:'
                      ' %s', result.status, result.output)
