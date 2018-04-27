# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.cros import chrome_binary_test
from autotest_lib.client.cros.graphics import graphics_utils

class graphics_Chrome(graphics_utils.GraphicsTest,
                      chrome_binary_test.ChromeBinaryTest):
    """Runs a given Chrome unittests binary."""
    version = 1

    @chrome_binary_test.nuke_chrome
    def run_once(self, unittests_binary_name, timeout):
        logging.debug('Starting %s', unittests_binary_name)
        try:
            self.run_chrome_test_binary(unittests_binary_name,
                                        timeout=timeout)
        except error.CmdTimeoutError:
            raise error.TestFail('Failed: timeout running %s' %
                                 unittests_binary_name)
