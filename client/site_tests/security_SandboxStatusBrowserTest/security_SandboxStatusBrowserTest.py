# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import chrome_test


class security_SandboxStatusBrowserTest(chrome_test.ChromeBinaryTest):
    """Runs SandboxStatusBrowserTest browser test."""

    version = 1
    binary_to_run = 'browser_tests'
    browser_test_args = '--gtest_filter=SandboxLinuxTest.SandboxStatus'


    def initialize(self):
        chrome_test.ChromeBinaryTest.initialize(self,
                                                nuke_browser_norestart=False)


    def run_once(self):
        last_error_message = None

        try:
            self.run_chrome_binary_test(self.binary_to_run,
                                        self.browser_test_args,
                                        as_chronos=True)
        except error.TestFail as test_error:
            # We only track |last_error_message| as we rely on gtest_runnner
            # to parse the failures for us when run. Right now all this
            # suppresses is multiple browser_tests failed messages.
            last_error_message = test_error.message

        if last_error_message:
            raise error.TestFail(last_error_message)
