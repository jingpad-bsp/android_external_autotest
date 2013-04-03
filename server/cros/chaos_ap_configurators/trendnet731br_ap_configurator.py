# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import trendnet_ap_configurator

from selenium.common.exceptions import WebDriverException

class Trendnet731brAPConfigurator(trendnet_ap_configurator.
                                  TrendnetAPConfigurator):
    """Derived class to control the Trendnet TEW-731BR."""


    def __init__(self, ap_config=None):
        super(Trendnet731brAPConfigurator, self).__init__(ap_config=ap_config)

    def navigate_to_page(self, page_number):
        # Navigate to login page before opening any other page
        self.navigate_to_login_page()
        if page_number == 1:
            page_url = ''.join([self.admin_interface_url,
                                  "/wireless_basic.htm"])
            self.get_url(page_url, page_title='TRENDNET')
        if page_number == 2:
            page_url = ''.join([self.admin_interface_url,
                                  "/wireless_auth.htm"])
            self.get_url(page_url, page_title='TRENDNET')


    def navigate_to_login_page(self):
        self.get_url(self.admin_interface_url, page_title='Login')
        self.wait_for_object_by_id('login_n')
        self.set_content_of_text_field_by_id('admin', 'login_n',
                                                 abort_check=True)
        self.set_content_of_text_field_by_id('password', 'login_pass',
                                                abort_check=True)
        self.click_button_by_xpath('//input[@value="Login"]')


    def _set_ssid(self, ssid):
        self.set_content_of_text_field_by_id(ssid, 'show_ssid')


    def save_page(self, page_number):
         if page_number == 1:
            xpath = ('//input[@type="button" and @value="Apply"]')
         elif page_number == 2:
            xpath = ('//input[@type="button" and @value="Apply"]')
         self.click_button_by_xpath(xpath, alert_handler=self._alert_handler)
         self.wait_for_progress_bar()
         xpath = ('//input[@type="button" and @value="Continue"]')
         self.click_button_by_xpath(xpath, alert_handler=self._alert_handler)


    def _set_security_disabled(self):
        self.wait_for_object_by_xpath('//select[@name="wep_type"]')
        self.select_item_from_popup_by_id(' Disable ','wep_type')


    def get_supported_modes(self):
        return [{'band': self.band_2ghz,
                 'modes': [self.mode_b,
                           self.mode_g,
                           self.mode_n,
                           self.mode_b | self.mode_g,
                           self.mode_b | self.mode_g | self.mode_n]}]


    def _set_mode(self, mode, band=None):
        # Different bands are not supported so we ignore.
        # Create the mode to popup item mapping
        mode_mapping = {self.mode_b | self.mode_g | self.mode_n:
                        '2.4Ghz 802.11b/g/n mixed mode',
                        self.mode_n: '2.4Ghz 802.11n only mode',
                        self.mode_b: '2.4Ghz 802.11b only mode',
                        self.mode_g: '2.4Ghz 802.11g only mode',
                        self.mode_b | self.mode_g:
                        '2.4Ghz 802.11b/g mixed mode'}
        mode_name = ''
        if mode in mode_mapping.keys():
            mode_name = mode_mapping[mode]
        else:
            raise RuntimeError('The mode selected %d is not supported by router'
                               ' %s.', hex(mode), self.get_router_name())
        self.select_item_from_popup_by_id(mode_name, 'dot11_mode')

    def get_supported_bands(self):
            return [{'band': self.band_2ghz, 'channels': range(1, 12)}]


    def _set_channel(self, channel):
        position = self._get_channel_popup_position(channel)
        channel_choices = ['1', '2', '3', '4', '5',
                           '6', '7', '8', '9', '10', '11']
        self.select_item_from_popup_by_id(channel_choices[position],
                                          'wlan0_channel_t')

    def _set_visibility(self, visible=True):
        # value=1 is visible; value=0 is invisible
        int_value = int(visible)
        xpath = ('//input[@value="%d" and @name="wlan0_ssid_broadcast"]' %
                  int_value)
        self.click_button_by_xpath(xpath, alert_handler=self._alert_handler)


    def _set_security_wep(self, key_value, authentication):
        self.wait_for_object_by_xpath('//select[@name="wep_type"]')
        self.select_item_from_popup_by_id(' WEP ','wep_type')
        # This router doesn not support ASCII passphrase for
        # generating hex key.Converting ASCII to hex before setting
        self.set_content_of_text_field_by_id(key_value.encode("hex"),
                                             'key1_64_hex')


    def _set_security_wpapsk(self, shared_key, update_interval=1800):
        self.wait_for_object_by_xpath('//select[@name="wep_type"]')
        self.select_item_from_popup_by_id(' WPA ','wep_type')
        self.set_content_of_text_field_by_id(shared_key,
                                             'wlan0_psk_pass_phrase')
        self.set_content_of_text_field_by_id(shared_key, 'wpapsk2')

    def _alert_handler(self, alert):
        """Checks for any modal dialogs which popup to alert the user and
        either raises a RuntimeError or ignores the alert.

        Args:
          alert: The modal dialog's contents.
        """
        text = alert.text
        if 'To disable SSID Broadcast will cause WPS not work' in text:
            alert.accept()
        else:
            raise RuntimeError('We have an unhandled alert: %s' % text)

