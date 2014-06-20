# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.ui import ui_test_base
from autotest_lib.client.common_lib import error


class ui_SettingsPage(ui_test_base.ui_TestBase):
    """ Collects screenshots of the settings page.

    See comments on parent class for overview of how things flow.

    """

    @property
    def test_area(self):
        return 'settings_page'


    def capture_screenshot(self, filepath):
        """
        Take a screenshot of the settings page.

        Implements the abstract method capture_screenshot

        @param filepath: string, complete path to save screenshot to.

        """
        with chrome.Chrome() as cr:
            tab = cr.browser.tabs[0]

            tab.Navigate('chrome://settings/')

            tab.WaitForDocumentReadyStateToBeComplete()

            if not tab.screenshot_supported:
                raise error.TestError('Tab did not support taking screenshots')

            tab.Screenshot().WritePngFile(filepath)


    def run_once(self):
        """ Called by autotest. Calls the parent template method that runs test.

        """
        self.run_screenshot_comparison_test()


