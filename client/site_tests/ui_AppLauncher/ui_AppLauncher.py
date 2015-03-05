# Copyright (c) 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.graphics import graphics_utils
from autotest_lib.client.cros.ui import ui_test_base


class ui_AppLauncher(ui_test_base.ui_TestBase):
    """
    Collects screenshots of the App Launcher.
    See comments on parent class for overview of how things flow.

    """

    def capture_screenshot(self, filepath):
        """
        Take a screenshot of the App Launcher page.

        Implements the abstract method capture_screenshot

        @param filepath: string, Complete path to save the screenshot to.

        """

        # Login and load the default apps
        with chrome.Chrome(disable_default_apps=False) as cr:

            # minimize the Chrome window
            graphics_utils.press_key_X('alt+minus')

            # open the launcher using the search key
            graphics_utils.press_key_X('super')

            # Open the 'All Apps' folder
            for x in xrange(0, 7):
                graphics_utils.press_key_X('Tab')
                time.sleep(0.5)

            graphics_utils.press_key_X('Return')
            time.sleep(0.5)

            # Take a screenshot and crop to just the launcher
            w, h = graphics_utils.get_display_resolution()
            box = (self.width, self.height, w - self.width, h - self.height)
            graphics_utils.take_screenshot_crop(filepath, box)


    def run_once(self, width, height):
        self.width = width
        self.height = height

        self.run_screenshot_comparison_test()

