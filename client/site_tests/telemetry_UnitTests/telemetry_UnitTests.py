# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, sys

from telemetry.unittest import gtest_progress_reporter
from telemetry.unittest import run_tests

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

TOOLS_BASE_DIR = '/usr/local/telemetry/src/tools/'
TELEMETRY_BASE_DIR = os.path.join(TOOLS_BASE_DIR, 'telemetry')
TELEMETRY_SUBDIR = os.path.join(TELEMETRY_BASE_DIR, 'telemetry')
PERF_BASE_DIR = os.path.join(TOOLS_BASE_DIR, 'perf')


class LoggingOutputStream(object):
    """A file-like object that buffers lines and sends them to logging.info."""
    def __init__(self):
        self._buffer = []

    def write(self, s):
        """Buffer a string write. Log it when we encounter a newline.

        @param s: The string to write to this stream.
        """
        if '\n' in s:
            segments = s.split('\n')
            segments[0] = ''.join(self._buffer + [segments[0]])
            log_level = logging.getLogger().getEffectiveLevel()
            try:  # TODO(dtu): We need this because of crbug.com/394571
                logging.getLogger().setLevel(logging.INFO)
                for line in segments[:-1]:
                    logging.info(line)
            finally:
                logging.getLogger().setLevel(log_level)
            self._buffer = [segments[-1]]
        else:
            self._buffer.append(s)

    def flush(self):
        """Dummy implementation of file flush."""


class TestSpec(object):
    """Test specification class with directory paths, etc."""
    def __init__(self, test_type, root, top_level_dir, tests):
        self.test_type = test_type
        self.root = root
        self.top_level_dir = top_level_dir
        self.tests = tests
        self.num_errors = 0

    def error_string(self):
        """Printable error string. Returns empty string if no errors."""
        if self.num_errors:
            return ('%d %s unit tests failed.\n' %
                    (self.num_errors, self.test_type))
        return ''

    @property
    def empty(self):
        """Returns False if this test spec has any tests."""
        return len(self.tests) == 0


class telemetry_UnitTests(test.test):
    """This is a client side wrapper for the Telemetry unit tests."""
    version = 1

    def _run_tests(self, browser_type, test_spec):
        """run unit tests in given directory and browser type.

        @param browser_type: The string type of browser to use, e.g., 'system'.
        @param test_spec: Object of type TestSpec.

        """
        if test_spec.empty:
            return
        logging.info('Running %s unit tests with browser_type "%s".',
                     test_spec.test_type, browser_type)
        sys.path.append(test_spec.top_level_dir)

        output_formatters = [
            gtest_progress_reporter.GTestProgressReporter(LoggingOutputStream())]
        run_tests.config = run_tests.Config(
            test_spec.top_level_dir, [test_spec.root], output_formatters)
        test_spec.num_errors = run_tests.RunTestsCommand.main(
            ['--browser', browser_type] + test_spec.tests)

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
