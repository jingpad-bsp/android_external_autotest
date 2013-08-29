# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, StringIO, sys

from telemetry.unittest import gtest_testrunner, run_tests

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


TELEMETRY_BASE_DIR = '/usr/local/telemetry/src/tools/telemetry'
UNIT_TEST_SUBDIR = 'telemetry'


class telemetry_UnitTests(test.test):
    """This is a client side wrapper for the Telemetry unit tests."""
    version = 1


    def run_once(self, browser_type):
        """
        Runs the Telemetry unit tests.

        @param browser_tye: The string type of browser to use, e.g., 'system'.

        """
        logging.info('Running the Telemetry unit tests with '
                     'browser_type "%s".', browser_type)

        # Capture the Telemetry output when running the unit tests.
        capturer = StringIO.StringIO()
        sys.stdout = capturer
        runner = gtest_testrunner.GTestTestRunner(print_result_after_run=False)
        run_tests.Main(['--browser=' + browser_type], UNIT_TEST_SUBDIR,
                       TELEMETRY_BASE_DIR, runner)

        if runner.result:
            # The PrintSummary() below is captured in the test debug log file.
            runner.result.PrintSummary()

        sys.stdout = sys.__stdout__  # Restore sys.stdout.
        logging.info(capturer.getvalue())  # Log the Telemetry output.
        capturer.close()

        if runner.result:
            if runner.result.num_errors:
                raise error.TestFail(
                        '%d unit tests failed.' % runner.result.num_errors)
            else:
                logging.info('All %d unit tests passed.',
                             len(runner.result.successes))
        else:
            raise error.TestFail('No results found.')
