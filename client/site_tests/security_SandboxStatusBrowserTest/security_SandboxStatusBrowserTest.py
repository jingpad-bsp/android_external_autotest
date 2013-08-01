# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import chrome_test


class security_SandboxStatusBrowserTest(chrome_test.ChromeBinaryTest):
    """Runs sandbox browser tests."""

    version = 1
    binary_to_run = 'browser_tests'
    # These will be passed to separate runs of |binary_to_run|
    # using 'gtest_filter'.
    tests_to_run = ['SandboxLinuxTest.SandboxStatus',
                    'SandboxStatusUITest*']


    def initialize(self):
        chrome_test.ChromeBinaryTest.initialize(self,
                                                nuke_browser_norestart=False)


    def run_once(self):
        test_failures = {}

        for test in self.tests_to_run:
            current_log_line = "Running test '%s'" % test
            logging.info(current_log_line)

            try:
                self.run_chrome_binary_test(self.binary_to_run,
                                            '--gtest_filter=' + test,
                                            as_chronos=False)
            except error.TestFail as test_failure:
                test_failures[test] = test_failure.message

        if len(test_failures) > 0:
            for failure, message in test_failures.iteritems():
                failed_log_line = "Test '%s' failed: '%s'" % (failure, message)
                logging.error(failed_log_line)

            raise error.TestFail("One or more browser tests failed: " +
                                 ", ".join(test_failures.keys()))
