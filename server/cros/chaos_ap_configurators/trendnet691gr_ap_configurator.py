# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import trendnet_ap_configurator


class Trendnet691grAPConfigurator(trendnet_ap_configurator.
                                  TrendnetAPConfigurator):
    """Derived class to control the Trendnet TEW-691GR."""


    def save_page(self, page_number):
        if page_number == 1:
            xpath = ('//input[@type="submit" and @value="Apply"]')
        elif page_number == 2:
            xpath = ('//input[@class="button_submit" and @value="Apply"]')
        self.click_button_by_xpath(xpath)
        # Wait for the settings progress bar to save the setting.
        self.wait_for_progress_bar()
        # Then reboot the device if told to.
        reboot_button = '//input[@value="Reboot the Device"]'
        if self.object_by_xpath_exist(reboot_button):
            self.click_button_by_xpath(reboot_button)
            self.wait_for_progress_bar()
