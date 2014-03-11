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


class TestSpec(object):
    """Test specification class with directory paths, etc."""
    def __init__(self, test_type, root, top_level_dir, tests):
        self.test_type = test_type
        self.root = root
        self.top_level_dir = top_level_dir
        self.tests = tests
        self.num_errors = 0
        self.error_details = ''

    def error_string(self):
        """Printable error string. Returns empty string if no errors."""
        if self.num_errors:
            return ('%d %s unit tests failed:\n%s' %
                    (self.num_errors, self.test_type,
                    self.error_details))
        return ''


class telemetry_UnitTests(test.test):
    """This is a client side wrapper for the Telemetry unit tests."""
    version = 1

    def _run_tests(self, browser_type, test_spec):
        """run unit tests in given directory and browser type.

        @param browser_type: The string type of browser to use, e.g., 'system'.
        @param test_spec: Object of type TestSpec.

        """
        logging.info('Running %s unit tests with browser_type "%s".',
                     test_spec.test_type, browser_type)
        sys.path.append(test_spec.root)
        # Capture the Telemetry output when running the unit tests.
        capturer = StringIO.StringIO()
        sys.stdout = capturer
        runner = gtest_testrunner.GTestTestRunner(print_result_after_run=False)
        for test in test_spec.tests:
            run_tests.Main(['--browser=%s' % browser_type, test],
                           test_spec.root, test_spec.top_level_dir, runner)

        if runner.result:
            # The PrintSummary() below is captured in the test debug log file.
            runner.result.PrintSummary()

        sys.stdout = sys.__stdout__  # Restore sys.stdout.
        test_output = capturer.getvalue()
        logging.info(test_output)  # Log the Telemetry output.
        capturer.close()

        if runner.result:
            if runner.result.num_errors:
                all_errors = runner.result.errors[:]
                all_errors.extend(runner.result.failures)
                for (test_name, error_string) in all_errors:
                    test_spec.error_details += '%s\n%s\n' % (test_name,
                                                             error_string)
                test_spec.num_errors = runner.result.num_errors
                logging.error(test_spec.error_string())
            else:
                logging.info('All %d %s unit tests passed.',
                             len(runner.result.successes), test_spec.test_type)
        elif test_spec.tests:
            raise error.TestFail('No results found.')


    def run_once(self, browser_type, unit_tests, perf_tests):
        """
        Runs telemetry/perf unit tests.

        @param browser_tye: The string type of browser to use, e.g., 'system'.

        """
        error_str = ''
        test_specs = [
            TestSpec('telemetry', TELEMETRY_SUBDIR, TELEMETRY_BASE_DIR,
                     unit_tests),
            TestSpec('perf', PERF_BASE_DIR, PERF_BASE_DIR, perf_tests),
        ]

        for test_spec in test_specs:
            self._run_tests(browser_type, test_spec)
            error_str += test_spec.error_string()
        if error_str:
            raise error.TestFail(error_str)
