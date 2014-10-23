# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.graphics import graphics_utils
from autotest_lib.client.cros.ui import ui_test_base


class ui_SystemTray(ui_test_base.ui_TestBase):
    """
    Collects system tray screenshots.

    See comments on parent class for overview of how things flow.

    """

    @property
    def test_area(self):
        return 'system_tray'

    def capture_screenshot(self, filepath):
        """
        Sets the portion of the screenshot to crop.
        Calls into take_screenshot_crop to take the screenshot and crop it.

        self.logged_in controls which logged-in state we are testing when we
        take the screenshot.

        if None, we don't login at all
        if True, we login as the test user
        if False, we login as guest

        @param filepath: path, fullpath to where the screenshot will be saved to

        """

        w, h = graphics_utils.get_display_resolution()
        box = (w - self.width, h - self.height, w, h)

        if self.logged_in is None:
            graphics_utils.take_screenshot_crop(filepath, box)
            return

        with chrome.Chrome(logged_in=self.logged_in):
            graphics_utils.take_screenshot_crop(filepath, box)

    def run_once(self, width, height, logged_in=None):
        """
        Called by autotest. Calls the parent template method that runs
        test.

        """

        # store values passed in from control file.
        # we will use them in capture_screenshot() which will get called as
        # part of run_screenshot_comparison_test() - the parent's method.

        self.width = width
        self.height = height
        self.logged_in = logged_in

        # see parent for implementation!
        self.run_screenshot_comparison_test()
