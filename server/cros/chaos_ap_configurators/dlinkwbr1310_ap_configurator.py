# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import time
import urlparse

import ap_configurator
from selenium.common.exceptions import TimeoutException as \
    SeleniumTimeoutException

class DLinkwbr1310APConfigurator(ap_configurator.APConfigurator):


    def __init__(self, router_dict):
        super(DLinkwbr1310APConfigurator, self).__init__(router_dict)
        self.security_disabled = 'Disable Wireless Security (not recommended)'
        self.security_wep = 'Enable WEP Wireless Security (basic)'
        self.security_wpapsk = 'Enable WPA-Personal Wireless Security \
                               (enhanced)'
        self.security_wpa2psk = 'Enable WPA2 Wireless Security (enhanced)'
        self.wep_key_type = 'ASCII'


    def _open_landing_page(self):
        page_url = urlparse.urljoin(self.admin_interface_url,'index.htm')
        self.driver.get(page_url)
        page_name = os.path.basename(self.driver.current_url)
        xpath = '//input[@name="login_name"]'
        def wait_for_login(xpath):
            # Waits for login screen to become available.
            # Args: xpath: the xpath of the element to wait for.
            # Login screen comes up for the first time after doing power_up.
            # After that we are directed to wireless_settings page.
            ret = None
            try:
               self.wait.until(lambda _: self.driver.find_element_by_xpath
                               (xpath))
               ret = self.driver.find_element_by_xpath(xpath)
            except SeleniumTimeoutException, e:
               pass
            return ret
        if page_name == 'index.htm' and wait_for_login(xpath):
              self.set_content_of_text_field_by_xpath('admin', xpath,
                                                      abort_check=False)
              pwd = '//input[@name="login_pass"]'
              self.set_content_of_text_field_by_xpath('password', pwd,
                                                      abort_check=False)
              button = '//input[@name="login"]'
              self.click_button_by_xpath(button)
        self._wireless_settings()


    def _wireless_settings(self):
        wlan = '//a[text()="Wireless settings"]'
        self.wait_for_object_by_xpath(wlan)
        self.click_button_by_xpath(wlan)


    def get_supported_bands(self):
        return [{'band': self.band_2ghz,
                 'channels': ['01', '02', '03', '04', '05', '06',
                              '07', '08', '09', '10', '11']}]


    def get_supported_modes(self):
        return [{'band': self.band_2ghz, 'modes': [self.mode_g, self.mode_b]}]


    def get_number_of_pages(self):
        return 1


    def is_security_mode_supported(self, security_mode):
        return security_mode in (self.security_disabled,
                                 self.security_wpapsk,
                                 self.security_wep)


    def navigate_to_page(self, page_number):
        # All settings are on the same page, so we always open the config page
        self._open_landing_page()


    def save_page(self, page_number):
        # All settings are on the same page, we can ignore page_number
        self.click_button_by_xpath('//input[@name="button"]')
        progress_value = self.wait_for_object_by_id("wTime")
        # Give the router 40 secs to update.
        for i in xrange(60):
            page_name = os.path.basename(self.driver.current_url)
            time.sleep(0.5)
            if page_name == 'wireless.htm':
                break


    def set_mode(self, mode_enable=True):
        self.add_item_to_command_list(self._set_mode, (mode_enable,), 1, 900)


    def _set_mode(self, mode_enable=True):
        # For dlinkwbr1310, 802.11g is the only available mode.
        logging.info('This router (%s) does not support multiple modes.' %
                     self.get_router_name())
        return None


    def set_radio(self, enabled=True):
        logging.info('This router (%s) does not support radio.' %
                     self.get_router_name())
        return None


    def set_ssid(self, ssid):
        self.add_item_to_command_list(self._set_ssid, (ssid,), 1, 900)


    def _set_ssid(self, ssid):
        self.set_content_of_text_field_by_id(ssid, 'ssid')


    def set_channel(self, channel):
        self.add_item_to_command_list(self._set_channel, (channel,), 1, 900)


    def _set_channel(self, channel):
        channel_ch = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11']
        xpath = '//select[@name="channel"]'
        self.select_item_from_popup_by_xpath(channel_ch[channel], xpath)


    def set_band(self, band):
        logging.info('This router (%s) does not support multiple bands.' %
                     self.get_router_name())
        return None


    def set_security_disabled(self):
        self.add_item_to_command_list(self._set_security_disabled, (), 1, 900)


    def _set_security_disabled(self):
        self.select_item_from_popup_by_id(self.security_disabled, 'wep_type')


    def set_security_wep(self, key_value, authentication):
        self.add_item_to_command_list(self._set_security_wep,
                                      (key_value, authentication), 1, 900)


    def _set_security_wep(self, key_value, authentication):
        popup = '//select[@name="wep_type"]'
        self.wait_for_object_by_xpath(popup)
        self.select_item_from_popup_by_xpath(self.security_wep, popup)
        key_type = '//select[@name="wep_key_type"]'
        self.select_item_from_popup_by_xpath(self.wep_key_type, key_type)
        text_field = '//input[@name="key1"]'
        self.set_content_of_text_field_by_xpath(key_value, text_field,
                                                abort_check=True)


    def set_security_wpapsk(self, shared_key, update_interval=None):
        self.add_item_to_command_list(self._set_security_wpapsk,
                                      (shared_key, update_interval), 1, 900)


    def _set_security_wpapsk(self, shared_key, update_interval=None):
        popup = '//select[@name="wep_type"]'
        self.wait_for_object_by_xpath(popup)
        key_field1 = '//input[@name="wpapsk1"]'
        key_field2 = '//input[@name="wpapsk2"]'
        self.select_item_from_popup_by_xpath(self.security_wpa2psk, popup,
                                             wait_for_xpath=key_field1)
        self.set_content_of_text_field_by_xpath(shared_key, key_field1,
                                                abort_check=False)
        self.set_content_of_text_field_by_xpath(shared_key, key_field2,
                                                abort_check=False)


    def set_visibility(self, visible=True):
        self.add_item_to_command_list(self._set_visibility, (visible,), 1, 900)


    def _set_visibility(self, visible=True):
        xpath = '//input[@name="ssidBroadcast"]'
        self.set_check_box_selected_by_xpath(xpath, selected=True)
