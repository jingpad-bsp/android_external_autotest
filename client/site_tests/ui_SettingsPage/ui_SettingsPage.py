# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.ui import ui_test_base
from autotest_lib.client.common_lib import error
from telemetry.image_processing import image_util


class ui_SettingsPage(ui_test_base.ui_TestBase):
    """
    Collects screenshots of the settings page.
    See comments on parent class for overview of how things flow.

    """

    def capture_screenshot(self, filepath):
        """
        Takes a screenshot of the settings page.

        A mask is then drawn over the profile picture. This test runs only
        on link at the moment so the dimensions provided are link specific.

        Implements the abstract method capture_screenshot.

        @param filepath: string, complete path to save screenshot to.

        """
        with chrome.Chrome() as cr:
            tab = cr.browser.tabs[0]
            tab.Navigate('chrome://settings')
            tab.WaitForDocumentReadyStateToBeComplete()

            if not tab.screenshot_supported:
                raise error.TestError('Tab did not support taking screenshots')

            screenshot = tab.Screenshot()
            if screenshot is None:
                raise error.TestFailure('Could not capture screenshot')

            image_util.WritePngFile(screenshot, filepath)


    def run_once(self, mask_points):
        self.mask_points = mask_points

        # Check if we should find mobile data in settings
        mobile = utils.system_output('modem status')
        if mobile:
            self.tagged_testname += '.mobile'
        self.run_screenshot_comparison_test()

