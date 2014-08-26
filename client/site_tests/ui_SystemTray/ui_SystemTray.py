# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import utils
from autotest_lib.client.cros.ui import ui_test_base


class ui_SystemTray(ui_test_base.ui_TestBase):
    """
    Collects system tray screenshots.

    See comments on parent class for overview of how things flow.

    """

    width = None
    height = None


    @property
    def test_area(self):
        return 'system_tray'


    def capture_screenshot(self, filepath):
        w, h = utils.get_dut_display_resolution()
        box = (w - ui_SystemTray.width, h - ui_SystemTray.height, w, h)
        utils.take_screenshot_crop(filepath, box)


    def run_once(self, width, height):
        """ Called by autotest. Calls the parent template method that runs test.

        """

        # store values passed in from control file.
        # we will use them in capture_screenshot() which will get called as
        # part of run_screenshot_comparison_test() - the parent's method.

        ui_SystemTray.width = width
        ui_SystemTray.height = height

        # see parent for implementation!
        self.run_screenshot_comparison_test()


