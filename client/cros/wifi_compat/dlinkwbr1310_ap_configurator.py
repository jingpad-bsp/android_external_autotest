# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import urlparse

import ap_configurator
from selenium.common.exceptions import TimeoutException as \
    SeleniumTimeoutException

class dlinkwbr1310APConfigurator(ap_configurator.APConfigurator):

    def __init__(self, router_dict):
        super(dlinkwbr1310APConfigurator, self).__init__(router_dict)
        self.security_disabled = 'Disable Wireless Security (not recommended)'
        self.security_wep = 'Enable WEP Wireless Security (basic)'
        self.security_wpa = 'Enable WPA-Personal Wireless Security (enhanced)'
        self.security_wpa2psk = 'Enable WPA2 Wireless Security (enhanced)'
        self.wep_key_type = 'ASCII'

    def _open_landing_page(self):
     page_url = urlparse.urljoin(self.admin_interface_url,'index.htm')
     self.driver.get(page_url)
     page_name = os.path.basename(self.driver.current_url)
     if page_name == 'index.htm':
         try:
            self.wait_for_object_by_xpath('//a[text()="Wireless settings"]')
         except SeleniumTimeoutException, e:
            raise SeleniumTimeoutException('Unable to navigate to the '
                                           'login or configuration page. '
                                           'WebDriver exception: %s', e)

    def _open_configuration_page(self):
        self._open_landing_page()
        if os.path.basename(self.driver.current_url) != 'index.htm':
            raise SeleniumTimeoutException('Taken to an unknown page %s' %
                os.path.basename(self.driver.current_url))
        wlan = '//a[text()="Wireless settings"]'
        self.wait_for_object_by_xpath(wlan)
        self.click_button_by_xpath(wlan)

    def get_number_of_pages(self):
        return 1

    def is_security_mode_supported(self, security_mode):
        return security_mode in (self.security_disabled,
                                 self.security_wpapsk,
                                 self.security_wep)

    def navigate_to_page(self, page_number):
        # All settings are on the same page, so we always open the config page
        self._open_configuration_page()

    def save_page(self, page_number):
        # All settings are on the same page, we can ignore page_number
        self.click_button_by_xpath('//input[@name="button"]')
        # If we did not make changes we are sent to the continue screen.
        continue_screen = True
        button_xpath = '//input[@name="button"]'
        try:
            self.wait_for_object_by_xpath(button_xpath)
        except selenium.common.exceptions.TimeoutException, e:
            continue_screen = False
        if continue_screen:
            self.click_button_by_xpath('//input[@name="button"]')
        # We will be returned to the landing page when complete
        self.wait_for_object_by_id("sidenavoff")

    def set_mode(self, mode_enable=True):
        # For dlinkwbr1310, 802.11g is the only available mode.
        self.add_item_to_command_list(self._set_mode, (mode_enable,), 1, 900)

    def _set_mode(self, mode_enable=True):
        xpath = '//input[@name="11gOnly"]'
        self.set_check_box_selected_by_xpath(xpath, selected=False)

    def set_radio(self, enabled=True):
        # If we are enabling we are activating all other UI components, do
        # it first. Otherwise we are turning everything off so do it last.
        if enabled:
            weight = 1
        else:
            weight = 1000
        self.add_item_to_command_list(self._set_radio, (enabled,), 1, weight)

    def _set_radio(self, enabled=True):
        # The radio checkbox for this router always has a value of 1.
        # So we use other methods to determine if the radio is on or not.
        # Check if the channel is disabled.
        temp = self.driver.find_element_by_xpath('//select[@name="channel"]')
        if temp.get_attribute('disabled') == 'true':
            radio_enabled = False
        else:
            radio_enabled = True
        if radio_enabled == enabled:
            # Nothing to do
            return
        self.set_check_box_selected_by_id('enable', selected=False)

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
        logging.debug('This router (%s) does not support multiple bands.' %
                      self.get_router_name())

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
        self.select_item_from_popup_by_xpath(self.security_wpa, popup,
                                             wait_for_xpath=key_field1)
        self.set_content_of_text_field_by_xpath(shared_key, key_field1,
                                                abort_check=False)
        self.set_content_of_text_field_by_xpath(shared_key, key_field2,
                                                abort_check=False)

    def set_visibility(self, visible=True):
        self.add_item_to_command_list(self._set_visibility, (visible,), 1, 900)

    def _set_visibility(self, visible=True):
        xpath = '//input[@name="ssidBroadcast"]'
        self.set_check_box_selected_by_xpath(xpath, selected=False)
