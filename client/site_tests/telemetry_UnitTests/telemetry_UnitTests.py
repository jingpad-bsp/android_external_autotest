# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

from telemetry.unittest import run_chromeos_tests


class telemetry_UnitTests(test.test):
    """This is a client side wrapper for the Telemetry unit tests."""
    version = 1


    def run_once(self, browser_type, unit_tests, perf_tests):
        """Runs telemetry/perf unit tests.

        @param browser_type: The string type of browser to use, e.g., 'system'.
        @param unit_tests: list of unit tests to run, [''] is all tests,
                           [] is no tests.
        @param perf_tests: list of perf unit tests to run, [''] is all tests,
                           [] is no tests.
        """
        error_str = run_chromeos_tests.RunTestsForChromeOS(browser_type,
                                                           unit_tests,
                                                           perf_tests)
        if error_str:
            raise error.TestFail(error_str)
