# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import urlparse
import ap_configurator

from selenium.common.exceptions import TimeoutException as \
      SeleniumTimeoutException
from selenium.common.exceptions import WebDriverException

class Netgear3700APConfigurator(ap_configurator.APConfigurator):
    """Derived class to control Netgear 3700 router."""

    def __init__(self, router_dict):
        super(Netgear3700APConfigurator, self).__init__(router_dict)
        self.security_disabled = 'Disabled'
        self.security_wep = 'WEP'
        self.security_wpapsk = 'WPA-PSK [TKIP]'
        self.security_wpa2psk = 'WPA2-PSK [AES]'
        self.security_wpapskmix = 'WPA-PSK [TKIP] + WPA2-PSK [AES]'
        self.security_wpaent = 'WPA/WPA2 Enterprise'
        self.mode_54 = 'Up to 54 Mbps'
        self.mode_130 = 'Up to 130 Mbps'
        self.mode_300 = 'Up to 300 Mbps'
        self.current_band = self.band_2ghz


    def _alert_handler(self, alert):
        """Checks for any modal dialogs which popup to alert the user and
        either raises a RuntimeError or ignores the alert.

        Args:
          alert: The modal dialog's contents.
        """
        text = alert.text
        #  We ignore warnings that we get when we disable visibility or security
        #  changed to WEP, WPA Personal or WPA Enterprise.
        if 'The WEP security can only be supported on one SSID' in text:
            alert.accept()
        else:
            alert.accept()
            raise RuntimeError('We have an unhandled alert: %s' % text)


    def _open_landing_page(self):
         self.driver.get(self.admin_interface_url)
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
            raise RuntimeError('Invalid url %s' % self.driver.current_url)


    def _get_settings_page(self):
        frame1 = self.driver.find_element_by_xpath('//frame[@name="contents"]')
        frame2 = self.driver.switch_to_frame(frame1)
        xpath = '//a[text()="Wireless Settings"]'
        self.click_button_by_xpath(xpath)
        default = self.driver.switch_to_default_content()
        setframe = self.driver.find_element_by_xpath(
                   '//frame[@name="formframe"]')
        settings = self.driver.switch_to_frame(setframe)


    def get_number_of_pages(self):
        return 1


    def get_supported_bands(self):
        return [{'band': self.band_2ghz,
                 'channels': ['Auto', '01', '02', '03', '04', '05', '06', '07',
                             '08', '09', '10', '11']},
                {'band': self.band_5ghz,
                 'channels': ['36', '40', '44', '48', '149', '153',
                              '157', '161']}]


    def get_supported_modes(self):
        return [{'band': self.band_5ghz,
                 'modes': [self.mode_54, self.mode_130, self.mode_300]},
                {'band': self.band_2ghz,
                 'modes': [self.mode_54, self.mode_130, self.mode_300]}]


    def is_security_mode_supported(self, security_mode):
        return security_mode in (self.security_disabled, self.security_wpapsk,
                                 self.security_wep, self.security_wpa2psk,
                                 self.security_wpapskmix, self.security_wpaent)


    def navigate_to_page(self, page_number):
        self._open_configuration_page()
        self._get_settings_page()


    def save_page(self, page_number):
        self.click_button_by_xpath('//input[@name="Apply"]',
                                   alert_handler=self._alert_handler)


    def set_radio(self, enabled=True):
        logging.info('set_radio is not supported in Netgear 3700.')
        return None


    def _switch_to_default(self):
        self.driver.switch_to_default_content()
        self._get_settings_page()


    def set_ssid(self, ssid):
        self.add_item_to_command_list(self._set_ssid, (ssid,), 1, 900)


    def _set_ssid(self, ssid):
        self._switch_to_default()
        xpath = '//input[@maxlength="32" and @name="ssid"]'
        if self.current_band == self.band_5ghz:
            xpath = '//input[@maxlength="32" and @name="ssid_an"]'
        self.set_content_of_text_field_by_xpath(ssid, xpath, abort_check=True)


    def set_band(self, band):
        self.add_item_to_command_list(self._set_band, (band,), 1, 900)


    def _set_band(self, band):
        if band == self.band_5ghz:
            self.current_band = self.band_5ghz
        elif band == self.band_2ghz:
            self.current_band = self.band_2ghz
        else:
            raise RuntimeError('Invalid band sent %s' % band)


    def set_channel(self, channel):
        self.add_item_to_command_list(self._set_channel, (channel,), 1, 900)


    def _set_channel(self, channel):
        self._switch_to_default()
        channel_choices = ['Auto', '01', '02', '03', '04', '05', '06', '07',
                           '08', '09', '10', '11']
        xpath = '//select[@name="w_channel"]'
        if self.current_band == self.band_5ghz:
            xpath = '//select[@name="w_channel_an"]'
            channel_choices = ['36', '40', '44', '48', '149', '153',
                               '157', '161']
        self.select_item_from_popup_by_xpath(channel_choices[channel], xpath)


    def set_mode(self, mode):
        self.add_item_to_command_list(self._set_mode, (mode,), 1, 900)


    def _set_mode(self, mode):
        self._switch_to_default()
        xpath = '//select[@name="opmode"]'
        if self.current_band == self.band_5ghz:
            xpath = '//select[@name="opmode_an"]'
        self.select_item_from_popup_by_xpath(mode, xpath)


    def set_security_disabled(self):
        self.add_item_to_command_list(self._set_security_disabled, (), 2, 1000)


    def _set_security_disabled(self):
        self._switch_to_default()
        xpath = ('//select[@name="security_type" and @value="Disable"]')
        if self.current_band == self.band_5ghz:
            xpath = ('//select[@name="security_type_an" and @value="Disable"]')
        self.click_button_by_xpath(xpath)


    def set_security_wep(self, value, authentication):
        self.add_item_to_command_list(self._set_security_wep,
                                     (value, authentication), 1, 900)


    def _set_security_wep(self, value, authentication):
        self._switch_to_default()
        xpath = ('//input[@name="security_type" and @value="WEP"]')
        text = '//input[@name="passphraseStr"]'
        button = '//input[@name="Generate"]'
        if self.current_band == self.band_5ghz:
            xpath = ('//input[@name="security_type_an" and @value="WEP"]')
            text = '//input[@name="passphraseStr_an"]'
            button = '//input[@name="Generate_an"]'
        try:
            self.click_button_by_xpath(xpath, alert_handler=self._alert_handler)
        except Exception, e:
            raise RuntimeError('For WEP the mode should be 54Mbps. %s' % e)
        self.set_content_of_text_field_by_xpath(value, text, abort_check=True)
        self.click_button_by_xpath(button, alert_handler=self._alert_handler)


    def set_security_wpapsk(self, key):
        self.add_item_to_command_list(self._set_security_wpapsk, (key,), 1, 900)


    def _set_security_wpapsk(self, key):
        self._switch_to_default()
        xpath = ('//input[@name="security_type" and @value="WPA-PSK"]')
        text = '//input[@name="passphrase"]'
        if self.current_band == self.band_5ghz:
            xpath = ('//input[@name="security_type_an" and @value="WPA-PSK"]')
            text = '//input[@name="passphrase_an"]'
        try:
            self.click_button_by_xpath(xpath)
        except Exception, e:
            raise RuntimeError('For WPA-PSK the mode should be 54Mbps. %s' % e)
        self.set_content_of_text_field_by_xpath(key, text, abort_check=True)


    def set_visibility(self, visible=True):
        # We cannot reset visibility effectively as the checkbox doesn't change
        # values from 0 to 1.
        logging.info('set_visibility is not supported in Netgear 3700.')
        return None
