# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, StringIO, sys

from telemetry.core import browser_finder
from telemetry.core import browser_options
from telemetry.unittest import gtest_unittest_results
from telemetry.unittest import run_tests

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
        args = browser_options.BrowserFinderOptions()
        args.browser_type = browser_type
        args.CreateParser().parse_args([])  # Hack to update BrowserOptions.
        possible_browser = browser_finder.FindBrowser(args)
        tests = run_tests.DiscoverTests(
            [test_spec.root], test_spec.top_level_dir,
            possible_browser, test_spec.tests)
        runner = gtest_unittest_results.GTestTestRunner()
        # Capture the Telemetry output when running the unit tests.
        capturer = StringIO.StringIO()
        try:
            sys.stdout = capturer
            result = runner.run(tests, 1, args)
            test_output = capturer.getvalue()
        finally:
            sys.stdout = sys.__stdout__  # Restore sys.stdout.
            capturer.close()
        logging.info(test_output)  # Log the Telemetry output.

        if result.wasSuccessful():
            logging.info('All %d %s unit tests passed.',
                         len(result.successes), test_spec.test_type)
        else:
            for (test_name, error_string) in result.failures_and_errors:
                test_spec.error_details += '%s\n%s\n' % (test_name,
                                                         error_string)
            test_spec.num_errors = len(result.failures_and_errors)
            logging.error(test_spec.error_string())


    def run_once(self, browser_type, unit_tests, perf_tests):
        """
        Runs telemetry/perf unit tests.

        @param browser_type: The string type of browser to use, e.g., 'system'.

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
