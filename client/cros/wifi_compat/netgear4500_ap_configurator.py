# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import urlparse

import ap_configurator
import selenium.common.exceptions


class NetgearAPConfigurator(ap_configurator.APConfigurator):
    def __init__(self, router_dict):
        super(NetgearAPConfigurator, self).__init__(router_dict)
        self.mode_54 = 'Up to 54 Mbps'
        self.mode_217 = 'Up to 217 Mbps'
        self.mode_450 = 'Up to 450 Mbps'
        self.security_disabled = 'None'
        self.security_wep = 'WEP'
        self.security_wpapsk = 'WPA-PSK [TKIP]'
        self.security_wpa2psk = 'WPA2-PSK [AES]'
        self.current_band = self.band_2ghz

    def _alert_handler(self, alert):
        """Checks for any modal dialogs which popup to alert the user and
        either raises a RuntimeError or ignores the alert.

        Args:
          alert: The modal dialog's contents.
        """
        text = alert.text
        if 'WPA-PSK [TKIP] ONLY operates at \"Up to 54Mbps\"' in text:
           alert.accept()
           raise RuntimeError('Wrong mode selected. %s' % text)
        else:
           alert.accept()
           raise RuntimeError('We have an unhandled alert: %s' % text)

    def get_number_of_pages(self):
        return 1

    def get_supported_bands(self):
        return [{'band': self.band_2ghz,
                 'channels': ['Auto', '01', '02', '03', '04', '05', '06', '07',
                              '08', '09', '10', '11']},
                {'band': self.band_5ghz,
                 'channels': ['Auto', '36', '40', '44', '48', '149', '153',
                              '157', '161', '165']}]

    def get_supported_modes(self):
        return [{'band': self.band_5ghz,
                 'modes': [self.mode_54, self.mode_217, self.mode_450]},
                {'band': self.band_2ghz,
                 'modes': [self.mode_54, self.mode_217, self.mode_450]}]

    def is_security_mode_supported(self, security_mode):
        return security_mode in (self.security_disabled,
                                 self.security_wpapsk,
                                 self.security_wep)

    def navigate_to_page(self, page_number):
        if page_number != 1:
           raise RuntimeError('Invalid page number passed.  Number of pages '
                              '%d, page value sent was %d' %
                              (self.get_number_of_pages(), page_number))
        page_url = urlparse.urljoin(self.admin_interface_url,
                                    'WLG_wireless_dual_band.htm')
        self.driver.get(page_url)
        self.wait_for_object_by_xpath('//input[@name="ssid" and @type="text"]')

    def save_page(self, page_number):
        self.click_button_by_xpath('//button[@name="Apply" and @type="SUBMIT"]',
                                   alert_handler=self._alert_handler)

    def set_mode(self, mode, band=None):
        self.add_item_to_command_list(self._set_mode, (mode, band), 1, 900)

    def _set_mode(self, mode, band=None):
        mode_list = [self.mode_54, self.mode_217, self.mode_450]
        xpath = '//select[@name="opmode"]'
        if self.current_band == self.band_5ghz or band == self.band_5ghz:
            self.current_band = self.band_5ghz
            xpath = '//select[@name="opmode_an"]'
        if mode not in mode_list:
            raise RuntimeError('The mode selected %d is not supported by router'
                               ' %s.', hex(mode), self.get_router_name())
        self.select_item_from_popup_by_xpath(mode, xpath)

    def set_radio(self, enabled=True):
        #  We cannot turn off the radio in Netgear
        return None

    def set_ssid(self, ssid):
        self.add_item_to_command_list(self._set_ssid, (ssid,), 1, 900)

    def _set_ssid(self, ssid):
        xpath = '//input[@name="ssid"]'
        if self.current_band == self.band_5ghz:
           xpath = '//input[@name="ssid_an"]'
        self.set_content_of_text_field_by_xpath(ssid, xpath)

    def set_channel(self, channel):
        self.add_item_to_command_list(self._set_channel, (channel,), 1, 900)

    def _set_channel(self, channel):
        channel_choices = ['Auto', '01', '02', '03', '04', '05', '06', '07',
                           '08', '09', '10', '11']
        xpath = '//select[@name="w_channel"]'
        if self.current_band == self.band_5ghz:
           xpath = '//select[@name="w_channel_an"]'
           channel_choices = ['Auto', '36', '40', '44', '48', '149', '153',
                              '157', '161', '165']
        self.select_item_from_popup_by_xpath(channel_choices[channel - 1],
                                             xpath)

    def set_band(self, band):
        self.add_item_to_command_list(self._set_band, (band,), 1, 900)

    def _set_band(self, band):
        if band == self.band_5ghz:
           self.current_band = self.band_5ghz
        elif band == self.band_2ghz:
           self.current_band = self.band_2ghz
        else:
           raise RuntimeError('Invalid band sent %s' % band)

    def set_security_disabled(self):
        self.add_item_to_command_list(self._set_security_disabled, (), 1, 900)

    def _set_security_disabled(self):
        xpath = '//input[@name="security_type" and @value="Disable" and\
                 @type="radio"]'
        if self.current_band == self.band_5ghz:
           xpath = '//input[@name="security_type_an" and @value="Disable" and\
                    @type="radio"]'
        self.click_button_by_xpath(xpath, alert_handler=self._alert_handler)

    def set_security_wep(self, key_value, authentication):
        self.add_item_to_command_list(self._set_security_wep,
                                      (key_value, authentication), 1, 900)

    def _set_security_wep(self, key_value, authentication):
        xpath = '//input[@name="security_type" and @value="WEP" and\
                 @type="radio"]'
        text_field = '//input[@name="passphraseStr"]'
        button = '//button[@name="keygen"]'
        if self.current_band == self.band_5ghz:
            xpath = '//input[@name="security_type_an" and @value="WEP" and\
                     @type="radio"]'
            text_field = '//input[@name="passphraseStr_an"]'
            button = '//button[@name="Generate_an"]'
        try:
            self.wait_for_object_by_xpath(xpath)
            self.click_button_by_xpath(xpath, alert_handler=self._alert_handler)
        except Exception, e:
            raise RuntimeError('We got an exception %s. The mode should be'
                               ' \'Up to  54 Mbps\'.' % str(e))
        self.wait_for_object_by_xpath(text_field)
        self.set_content_of_text_field_by_xpath(key_value, text_field,
                                                abort_check=True)
        self.click_button_by_xpath(button, alert_handler=self._alert_handler)

    def set_security_wpapsk(self, shared_key, update_interval=1800):
        self.add_item_to_command_list(self._set_security_wpapsk,
                                      (shared_key, update_interval), 1, 900)

    def _set_security_wpapsk(self, shared_key, update_interval=1800):
        xpath = '//input[@name="security_type" and @value="WPA-PSK" and\
                 @type="radio"]'
        key_field = '//input[@name="passphrase"]'
        if self.current_band == self.band_5ghz:
           xpath = '//input[@name="security_type_an" and @value="WPA-PSK" and\
                    @type="radio"]'
           key_field = '//input[@name="passphrase_an"]'
        self.wait_for_object_by_xpath(xpath)
        self.click_button_by_xpath(xpath, alert_handler=self._alert_handler)
        self.wait_for_object_by_xpath(key_field)
        self.set_content_of_text_field_by_xpath(shared_key, key_field,
                                                abort_check=True)

    def set_visibility(self, visible=True):
        self.add_item_to_command_list(self._set_visibility, (visible,), 1, 900)

    def _set_visibility(self, visible=True):
        xpath = '//input[@name="ssid_bc" and @type="checkbox"]'
        if self.current_band == self.band_5ghz:
           xpath = '//input[@name="ssid_bc_an" and @type="checkbox"]'
        self.set_check_box_selected_by_xpath(xpath, selected=visible,
                                             wait_for_xpath=None,
                                             alert_handler=self._alert_handler)
