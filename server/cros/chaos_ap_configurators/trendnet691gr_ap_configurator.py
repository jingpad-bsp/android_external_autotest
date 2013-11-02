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


    def _set_security_wpapsk(self, shared_key, update_interval=1800):
        self.wait_for_object_by_id('security_mode')
        self.select_item_from_popup_by_id('WPA-PSK', 'security_mode',
                                          wait_for_xpath='id("passphrase")')
        self.set_content_of_text_field_by_id(shared_key, 'passphrase')
        self.set_content_of_text_field_by_id(update_interval,
                                             'keyRenewalInterval')
