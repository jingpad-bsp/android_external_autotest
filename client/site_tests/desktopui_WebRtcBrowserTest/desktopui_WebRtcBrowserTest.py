# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import chrome_test


class desktopui_WebRtcBrowserTest(chrome_test.ChromeBinaryTest):
    """Runs webrtc browser tests."""
    version = 1
    binary_to_run = 'browser_tests'
    browser_test_args = '--gtest_filter=WebrtcBrowserTest* --run-manual'

    def initialize(self):
        chrome_test.ChromeBinaryTest.initialize(self,
            nuke_browser_norestart=False)


    def run_once(self):
        """
        Runs browser tests using the chrome binary built in the initialize
        step, with the specified arguments.
        """
        # Load virtual webcam driver for devices that don't have a webcam.
        if utils.get_board() == 'stumpy':
            utils.load_module('vivi')
        last_error_message=None
        try:
            self.run_chrome_binary_test(self.binary_to_run,
                self.browser_test_args, as_chronos=False)
        except error.TestFail as test_error:
            # We only track the last_error message as we rely on gtest_runnner
            # to parse the failures for us when run. Right now all this
            # suppresses is multiple browser_tests failed messages.
            last_error_message = test_error.message

        if last_error_message:
            raise error.TestError(last_error_message)
