# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

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
        self.wait = WebDriverWait(self.driver, timeout=60)
        self.click_button_by_xpath('//input[@value="Reboot the Device"]')
        self.wait = WebDriverWait(self.driver, timeout=5)
        # Give the trendnet up to 2 minutes. The idea here is to end when the
        # reboot is complete.
        for i in xrange(240):
            progress_value = self.wait_for_object_by_id('progressValue')
            html = self.driver.execute_script('return arguments[0].innerHTML',
                                              progress_value)
            percentage = html.rstrip('%')
            if int(percentage) < 95:
                time.sleep(0.5)
            else:
                return

