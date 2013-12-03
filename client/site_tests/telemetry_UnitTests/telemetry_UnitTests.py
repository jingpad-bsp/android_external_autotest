# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, StringIO, sys

from telemetry.unittest import gtest_testrunner, run_tests

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

TOOLS_BASE_DIR = '/usr/local/telemetry/src/tools/'
TELEMETRY_BASE_DIR = os.path.join(TOOLS_BASE_DIR, 'telemetry')
TELEMETRY_SUBDIR = os.path.join(TELEMETRY_BASE_DIR, 'telemetry')
PERF_BASE_DIR = os.path.join(TOOLS_BASE_DIR, 'perf')


class telemetry_UnitTests(test.test):
    """This is a client side wrapper for the Telemetry unit tests."""
    version = 1


    def run_unit_tests(self, browser_type, start_dir, top_level_dir):
        """run unit tests in given directory and browser type.

        @param browser_type: The string type of browser to use, e.g., 'system'.
        @param start_dir: The directory to recursively search.
        @param top_level_dir: The top level of the package, for importing.

        """
        # Capture the Telemetry output when running the unit tests.
        capturer = StringIO.StringIO()
        sys.stdout = capturer
        runner = gtest_testrunner.GTestTestRunner(print_result_after_run=False)
        run_tests.Main(['--browser=' + browser_type], start_dir,
                       top_level_dir, runner)

        if runner.result:
            # The PrintSummary() below is captured in the test debug log file.
            runner.result.PrintSummary()

        sys.stdout = sys.__stdout__  # Restore sys.stdout.
        test_output = capturer.getvalue()
        logging.info(test_output)  # Log the Telemetry output.
        capturer.close()

        if runner.result:
            if runner.result.num_errors:
                error_details = ''
                all_errors = runner.result.errors[:]
                all_errors.extend(runner.result.failures)
                for (test_name, error_string) in all_errors:
                    error_details += '%s\n%s\n' % (test_name, error_string)
                raise error.TestFail('%d unit tests failed:\n%s' %
                                     (runner.result.num_errors, error_details))
            else:
                logging.info('All %d unit tests passed.',
                             len(runner.result.successes))
        else:
            raise error.TestFail('No results found.')


    def run_once(self, browser_type):
        """
        Runs the Telemetry unit tests.

        @param browser_tye: The string type of browser to use, e.g., 'system'.

        """
        logging.info('Running the Telemetry unit tests with '
                     'browser_type "%s".', browser_type)
        self.run_unit_tests(browser_type, TELEMETRY_SUBDIR, TELEMETRY_BASE_DIR)

        logging.info('Running the perf unit tests with '
                     'browser_type "%s".', browser_type)
        sys.path.append(PERF_BASE_DIR)
        self.run_unit_tests(browser_type, PERF_BASE_DIR, PERF_BASE_DIR)