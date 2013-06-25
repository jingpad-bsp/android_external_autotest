# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import trendnet_ap_configurator


class Trendnet691grAPConfigurator(trendnet_ap_configurator.
                                  TrendnetAPConfigurator):
    """Derived class to control the Trendnet TEW-691GR."""


    def save_page(self, page_number):
        super(Trendnet691grAPConfigurator, self).save_page(page_number)
        # Reboot the device.
        reboot_button = '//input[@value="Reboot the Device"]'
        if self.object_by_xpath_exist(reboot_button):
            self.click_button_by_xpath(reboot_button)
            self.wait_for_progress_bar()
