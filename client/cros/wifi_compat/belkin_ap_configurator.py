# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import time
import urlparse

import ap_configurator
from selenium.common.exceptions import TimeoutException as \
    SeleniumTimeoutException

class belkinAPConfigurator(ap_configurator.APConfigurator):

  def __init__(self, router_dict):
     super(belkinAPConfigurator, self).__init__(router_dict)
     self.security_disabled = 'Disabled'
     self.security_wep = '64bit WEP'
     self.security_wpapsk = 'WPA-PSK(no server)'
     self.authentication_psk = 'psk'
     self.authentication_wpa2 = 'WPA2'
     self.authentication_wpa1_wpa2 = 'WPA1WPA2'

  def _security_alert(self, alert):
     text = alert.text
     if "Invalid character" in text:
       alert.accept()
     else:
       raise RuntimeError('Invalid handler')

  def _open_landing_page(self):
     page_url = urlparse.urljoin(self.admin_interface_url,'home.htm')
     self.driver.get(page_url)
     page_name = os.path.basename(self.driver.current_url)
     if page_name == 'home.htm':
         try:
            self.wait_for_object_by_xpath('//a[text()="Wireless"]')
         except SeleniumTimeoutException, e:
            raise SeleniumTimeoutException('Unable to navigate to the '
                                           'login or configuration page. '
                                           'WebDriver exception: %s', e)

  def _open_configuration_page(self):
     self._open_landing_page()
     if os.path.basename(self.driver.current_url) == 'home.htm':
       xpath = '//a[text()="Wireless"]'
       self.click_button_by_xpath(xpath)
       xpath = '//input[@name="www_password"]'
       self.set_content_of_text_field_by_xpath('password', xpath,
                                               abort_check=True)
       self.click_button_by_id('submitBtn_submit')
     else:
       raise RuntimeError('Invalid url %s' %
                          os.path.basename(self.driver.current_url))

  def get_number_of_pages(self):
     return 2

  def is_security_mode_supported(self, security_mode):
        return security_mode in (self.security_disabled,
                                 self.security_wpapsk,
                                 self.security_wep)

  def navigate_to_page(self, page_number):
    self._open_configuration_page()
    if page_number == 1:
     page_url = urlparse.urljoin(self.admin_interface_url,'wireless_chan.htm')
     self.driver.get(page_url)
    elif page_number == 2:
     page_url = urlparse.urljoin(self.admin_interface_url,
                                 'wireless_encrypt_64.htm')
     self.driver.get(page_url)
    else:
     raise RuntimeError('Invalid page number passed. Number of pages '
                        '%d, page value sent was %d' %
                        (self.get_number_of_pages(), page_number))

  def save_page(self, page_number):
     self.click_button_by_id('submitBtn_apply',
                             alert_handler=self._security_alert)
     if os.path.basename(self.driver.current_url) == 'post.cgi':
       #Give belkin some time to save settings.
       time.sleep(5)
     else:
       raise RuntimeError('Settings not applied. Invalid page %s' %
                          os.path.basename(self.driver.current_url))
     if (os.path.basename(self.driver.current_url) == 'wireless_chan.htm' or
     'wireless_encrypt_64.htm' or 'wireless_wpa_psk_wpa2_psk.htm'
     or 'wireless_encrypt_no.htm'):
         self.driver.find_element_by_xpath('//a[text()="Logout"]')
         self.click_button_by_xpath('//a[text()="Logout"]')

  def set_ssid(self, ssid):
     self.add_item_to_command_list(self._set_ssid, (ssid,), 1, 900)

  def _set_ssid(self, ssid):
     # Belkin does not accept special characters for SSID.
     xpath = '//input[@name="wl_ssid"]'
     self.set_content_of_text_field_by_xpath(ssid, xpath, abort_check=False)

  def set_channel(self, channel):
     self.add_item_to_command_list(self._set_channel, (channel,), 1, 900)

  def _set_channel(self, channel):
     channel_choices = ['Auto', '1', '2', '3', '4', '5', '6', '7', '8',
                        '9', '10', '11']
     xpath = '//select[@name="wl_channel"]'
     self.select_item_from_popup_by_xpath(channel_choices[channel], xpath)

  def set_mode(self, mode):
     self.add_item_to_command_list(self._set_mode, (mode,), 1, 900)

  def _set_mode(self, mode):
     modes = ['802.11g&802.11b', '802.11n only', '802.11b&802.11g&802.11n']
     xpath = '//select[@name="wl_gmode"]'
     self.select_item_from_popup_by_xpath(modes[mode], xpath)

  def set_ch_width(self, channel_width):
     self.add_item_to_command_list(self._set_ch_width,(channel_width,), 1, 900)

  def _set_ch_width(self, channel_width):
     channel_choice = ['20MHz', '20/40MHz']
     xpath = '//select[@name="wl_cwmmode"]'
     self.select_item_from_popup_by_xpath(channel_choice[channel_width], xpath)

  def set_security_disabled(self):
     self.add_item_to_command_list(self._set_security_disabled, (), 2, 1000)

  def _set_security_disabled(self):
     xpath = '//select[@name="wl_sec_mode"]'
     self.select_item_from_popup_by_xpath(self.security_disabled, xpath)

  def set_security_wep(self, key_value, authentication):
     self.add_item_to_command_list(self._set_security_wep,
                                   (key_value, authentication), 2, 1000)

  def _set_security_wep(self, key_value, authentication):
     popup = '//select[@name="wl_sec_mode"]'
     self.wait_for_object_by_xpath(popup)
     text_field = '//input[@name="wep64pp"]'
     self.select_item_from_popup_by_xpath(self.security_wep, popup,
                                          wait_for_xpath=text_field)
     self.set_content_of_text_field_by_xpath(key_value, text_field,
                                             abort_check=True)
     button = self.driver.find_element_by_id('submitBtn_generate')
     button.click()

  def set_security_wpapsk(self, shared_key, update_interval=None):
     self.add_item_to_command_list(self._set_security_wpapsk,
                                   (shared_key, update_interval), 2, 900)

  def _set_security_wpapsk(self, shared_key, update_interval=None):
     popup = '//select[@name="wl_sec_mode"]'
     self.wait_for_object_by_xpath(popup)
     key_field = '//input[@name="wl_wpa_psk1"]'
     psk = '//select[@name="wl_auth"]'
     self.select_item_from_popup_by_xpath(self.security_wpapsk, popup,
                                          wait_for_xpath=key_field)
     self.select_item_from_popup_by_xpath(self.authentication_psk, psk,
                                          wait_for_xpath=None)
     self.set_content_of_text_field_by_xpath(shared_key, key_field,
                                             abort_check=False)

  def set_visibility(self, visible=True):
     self.add_item_to_command_list(self._set_visibility, (visible,), 1, 900)

  def _set_visibility(self, visible=True):
     xpath = '//input[@name="closed"]'
     self.set_check_box_selected_by_xpath(xpath, selected=False)
