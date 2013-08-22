# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import chrome_test


class security_SandboxLinuxUnittests(chrome_test.ChromeBinaryTest):
    """Runs sandbox_linux_unittests."""

    version = 1
    binary_to_run = 'sandbox_linux_unittests'


    def initialize(self):
        chrome_test.ChromeBinaryTest.initialize(self,
                                                nuke_browser_norestart=False)


    def run_once(self):
        try:
            self.run_chrome_binary_test(self.binary_to_run, '',
                                        as_chronos=True)

        except error.TestFail as test_failure:
            raise error.TestFail("%s failed: '%s'" % (self.binary_to_run,
                                                      test_failure.message))
