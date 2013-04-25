# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server import test
from autotest_lib.server.cros import telemetry_runner


class telemetry_Benchmarks(test.test):
    """Run a telemetry benchmark."""
    version = 1


    def run_once(self, host=None, benchmark=None, page_sets=None):
        """Run a telemetry benchmark over a given list of page_sets.

        @param host: host we are running telemetry on.
        @param benchmark: benchmark we want to run.
        @param page_sets: list of page sets we want to use with this benchmark.
        """
        failed_page_sets = []
        warned_page_sets = []
        telemetry = telemetry_runner.TelemetryRunner(host)
        for page_set in page_sets:
            try:
                telemetry.run_telemetry_benchmark(benchmark,
                                                  page_set,
                                                  keyval_writer=self)
            except error.TestWarn:
                logging.warn('%s exited with warning for page_set: %s',
                             benchmark, page_set)
                warned_page_sets.append(page_set)
            except error.TestFail:
                logging.error('%s failed for page_set: %s', benchmark,
                              page_set)
                failed_page_sets.append(page_set)
        if failed_page_sets:
            raise error.TestFail('%s failed for page_sets: %s. And warned'
                                 ' for page_sets: %s.'% (benchmark,
                                 failed_page_sets, warned_page_sets))
        if warned_page_sets:
            raise error.TestWarn('%s exited with warnings for page_sets:'
                                 ' %s.'% (benchmark, warned_page_sets))
