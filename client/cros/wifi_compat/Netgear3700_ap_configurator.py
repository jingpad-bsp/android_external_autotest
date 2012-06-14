# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import urlparse
import ap_configurator

from selenium.common.exceptions import TimeoutException as \
    SeleniumTimeoutException
from selenium.common.exceptions import WebDriverException

class Netgear3700APConfigurator(ap_configurator.APConfigurator):

  def __init__(self, router_dict):
     super(Netgear3700APConfigurator, self).__init__(router_dict)
     self.security_disabled = 'Disabled'
     self.security_wep = 'WEP'
     self.security_wpapsk = 'WPA Personal'
     self.security_wpa2psk = 'WPA2 Personal'
     self.security_wpa8021x = 'WPA Enterprise'
     self.security_wpa28021x = 'WPA2 Enterprise'

  def _open_landing_page(self):
     page_url = urlparse.urljoin(self.admin_interface_url,'index.htm')
     self.driver.get(page_url)
     page_name = os.path.basename(self.driver.current_url)
     if page_name == 'index.htm':
         try:
            self.wait_for_object_by_xpath('//frame[@name="contents"]')
         except SeleniumTimeoutException, e:
            raise SeleniumTimeoutException('Unable to navigate to the '
                                           'login or configuration page. '
                                           'WebDriver exception:%s', e)

  def _open_configuration_page(self):
     self._open_landing_page()
     if os.path.basename(self.driver.current_url) != 'index.htm':
        raise RuntimeError('Invalid url %s' %
                           os.path.basename(self.driver.current_url))

  def _get_settings_page(self):
     frame1 = self.driver.find_element_by_xpath('//frame[@name="contents"]')
     frame2 = self.driver.switch_to_frame(frame1)
     xpath = '//a[text()="Wireless Settings"]'
     self.click_button_by_xpath(xpath)
     default = self.driver.switch_to_default_content()
     setframe = self.driver.find_element_by_xpath('//frame[@name="formframe"]')
     settings = self.driver.switch_to_frame(setframe)

  def get_number_of_pages(self):
     return 1

  def is_security_mode_supported(self, security_mode):
        return security_mode in (self.security_disabled,
                                 self.security_wpapsk,
                                 self.security_wep)

  def navigate_to_page(self, page_number):
     self._open_configuration_page()

  def save_page(self, page_number):
     self.click_button_by_xpath('//input[@nme="Apply"]')

  def set_radio(self, enabled=True):
     self.add_item_to_command_list(self._set_radio, (enabled,), 1, 900)

  def _set_radio(self, enabled=True):
     # For this router we will enable radio for 2.4GHz only and configure
     # settings for 2.4GHz.
     self._open_configuration_page()
     frame1 = self.driver.find_element_by_xpath('//frame[@name="contents"]')
     frame2 = self.driver.switch_to_frame(frame1)
     xpath='//a[@href="WLG_adv.htm" and text()="Wireless Settings"]'
     self.click_button_by_xpath(xpath)
     self.driver.switch_to_default_content()
     setting = self.driver.find_element_by_xpath('//frame[@name="formframe"]')
     settings = self.driver.switch_to_frame(setting)
     xpath = '//input[@name="enable_ap"]'
     self.set_check_box_selected_by_xpath(xpath, selected=False)

  def _switch_to_default(self):
     self.driver.switch_to_default_content()
     self._get_settings_page()

  def set_ssid(self, ssid):
     self.add_item_to_command_list(self._set_ssid, (ssid,), 1, 900)

  def _set_ssid(self, ssid):
     self._set_radio(enabled=True)
     self._switch_to_default()
     xpath = '//input[@maxlength="32" and @name="ssid"]'
     self.set_content_of_text_field_by_xpath(ssid, xpath, abort_check=True)

  def set_channel(self, channel):
     self.add_item_to_command_list(self._set_channel, (channel,), 1, 900)

  def _set_channel(self, channel):
     self._set_radio(enabled=True)
     self._switch_to_default()
     channel_choices = ['Auto', '01', '02', '03', '04', '05', '06', '07', '08',
                        '09', '10', '11']
     xpath = '//select[@name="w_channel"]'
     self.select_item_from_popup_by_xpath(channel_choices[channel], xpath)

  def set_mode(self, mode):
     self.add_item_to_command_list(self._set_mode, (mode,), 1, 900)

  def _set_mode(self, mode):
     self._set_radio(enabled=True)
     self._switch_to_default()
     modes = ['Up to 54 Mbps', 'Up to 130 Mbps', 'Up to 300 Mbps']
     xpath = '//select[@name="opmode"]'
     self.select_item_from_popup_by_xpath(modes[mode], xpath)

  def set_security_disabled(self):
     self.add_item_to_command_list(self._set_security_disabled, (), 2, 1000)

  def _set_security_disabled(self):
     self._set_radio(enabled=True)
     self._switch_to_default()
     xpath = ('//select[@name="security_type" and @value="Disable"]')
     self.click_button_by_xpath(xpath)

  def set_security_wep(self, value, authentication):
     self.add_item_to_command_list(self._set_security_wep,
                                   (value, authentication), 1, 900)

  def _set_security_wep(self, value, authentication):
     self._set_radio(enabled=True)
     self._switch_to_default()
     xpath = ('//input[@name="security_type" and @value="WEP"]')
     self.click_button_by_xpath(xpath)
     xpath = '//input[@name="passphraseStr"]'
     self.set_content_of_text_field_by_xpath(value, xpath, abort_check=True)
     xpath = '//input[@value="Generate"]'
     self.click_button_by_xpath(xpath)

  def set_security_wpapsk(self, key):
     self.add_item_to_command_list(self._set_security_wpapsk, (key,), 1, 900)

  def _set_security_wpapsk(self, key):
     self._set_radio(enabled=True)
     self._switch_to_default()
     xpath = ('//input[@name="security_type" and @value="WPA-PSK"]')
     self.click_button_by_xpath(xpath)
     xpath = '//input[@name="passphrase"]'
     self.set_content_of_text_field_by_xpath(key, xpath, abort_check=True)

  def set_visibility(self, visible=True):
     self.add_item_to_command_list(self._set_visibility, (visible,), 1, 900)

  def _set_visibility(self, visible=True):
     self._set_radio(enabled=True)
     self._switch_to_default()
     xpath = '//input[@name="ssid_bc"]'
     self.set_check_box_selected_by_xpath(xpath, selected=False)
