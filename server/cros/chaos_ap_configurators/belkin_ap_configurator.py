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

class BelkinAPConfigurator(ap_configurator.APConfigurator):


    def __init__(self, router_dict):
        super(BelkinAPConfigurator, self).__init__(router_dict)
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
        xpath = '//a[text()="Login"]'
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
        if page_name == 'home.htm' and wait_for_login(xpath):
            self.click_button_by_xpath(xpath)
            xpath = '//input[@name="www_password"]'
            self.set_content_of_text_field_by_xpath('password', xpath,
                                                    abort_check=True)
            self.click_button_by_id('submitBtn_submit')
        else:
            return None


    def get_supported_bands(self):
        return [{'band': self.band_2ghz,
                 'channels': ['Auto', 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]}]


    def get_supported_modes(self):
        return [{'band': self.band_2ghz,
                 'modes': [self.mode_g | self.mode_b, self.mode_n,
                           self.mode_b | self.mode_g | self.mode_n]}]


    def get_number_of_pages(self):
        return 2


    def is_security_mode_supported(self, security_mode):
        return security_mode in (self.security_disabled,
                                 self.security_wpapsk,
                                 self.security_wep)


    def navigate_to_page(self, page_number):
        self._open_landing_page()
        if page_number == 1:
            page_url = urlparse.urljoin(self.admin_interface_url,
                                        'wireless_chan.htm')
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
            # Give belkin some time to save settings.
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
        # Invalid character: ~!@#$%^&*()={}[]|'\":;?/.,<>-
        xpath = '//input[@name="wl_ssid"]'
        self.set_content_of_text_field_by_xpath(ssid, xpath, abort_check=False)


    def set_channel(self, channel):
        self.add_item_to_command_list(self._set_channel, (channel,), 1, 900)


    def _set_channel(self, channel):
        position = self._get_channel_popup_position(channel)
        channel_choices = ['Auto', '1', '2', '3', '4', '5', '6', '7', '8',
                           '9', '10', '11']
        xpath = '//select[@name="wl_channel"]'
        self.select_item_from_popup_by_xpath(channel_choices[position], xpath)


    def set_mode(self, mode):
        self.add_item_to_command_list(self._set_mode, (mode,), 1, 900)


    def _set_mode(self, mode):
        mode_mapping = {self.mode_g | self.mode_b: '802.11g&802.11b',
                        self.mode_n: '802.11n only',
                        self.mode_b | self.mode_g | self.mode_n:
                        '802.11b&802.11g&802.11n'}
        mode_name = mode_mapping.get(mode)
        if not mode_name:
            raise RuntimeError('The mode %d not supported by router %s. ',
                               hex(mode), self.get_router_name())
        xpath = '//select[@name="wl_gmode"]'
        self.select_item_from_popup_by_xpath(mode_name, xpath)


    def set_ch_width(self, channel_width):
        self.add_item_to_command_list(self._set_ch_width,(channel_width,),
                                      1, 900)


    def _set_ch_width(self, channel_width):
        channel_choice = ['20MHz', '20/40MHz']
        xpath = '//select[@name="wl_cwmmode"]'
        self.select_item_from_popup_by_xpath(channel_choice[channel_width],
                                             xpath)


    def set_radio(self, enabled=True):
        logging.info('This router (%s) does not support radio' %
                     self.get_router_name())
        return None


    def set_band(self, band):
        logging.info('This router (%s) does not support multiple bands.' %
                     self.get_router_name())
        return None


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
        logging.info('Visibility is not supported for this router %s.' %
                     self.get_router_name())
        return None
