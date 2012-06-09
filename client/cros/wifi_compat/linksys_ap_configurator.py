# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import urlparse

import ap_configurator
import selenium.common.exceptions


class LinksysAPConfigurator(ap_configurator.APConfigurator):

    def __init__(self, router_dict):
        super(LinksysAPConfigurator, self).__init__(router_dict)
        # Overrides
        self.security_disabled = 'Disabled'
        self.security_wep = 'WEP'
        self.security_wpapsk = 'WPA Personal'
        self.security_wpa2psk = 'WPA2 Personal'
        self.security_wpa8021x = 'WPA Enterprise'
        self.security_wpa28021x = 'WPA2 Enterprise'

    def get_number_of_pages(self):
        return 2

    def get_supported_bands(self):
        return [{'band': self.k2GHz,
                 'channels': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]}]

    def get_supported_modes(self):
        return [{'band': self.band_2ghz,
                 'modes': [self.mode_b, self.mode_g, self.mode_b |
                           self.mode_g]}]

    def is_security_mode_supported(self, security_mode):
        return security_mode in (self.security_disabled,
                                 self.security_wpapsk,
                                 self.security_wep)

    def navigate_to_page(self, page_number):
        if page_number == 1:
            url = urlparse.urljoin(self.admin_interface_url, 'wireless.htm')
            self.driver.get(url)
        elif page_number == 2:
            url = urlparse.urljoin(self.admin_interface_url, 'WSecurity.htm')
            self.driver.get(url)
        else:
            raise RuntimeError('Invalid page number passed.  Number of pages '
                               '%d, page value sent was %d' %
                               (self.get_number_of_pages(), page_number))

    def save_page(self, page_number):
        self.wait_for_object_by_id('divBT1')
        button = self.driver.find_element_by_xpath('id("divBT1")')
        button.click()
        # Wait for the continue button
        continue_xpath = '//input[@value="Continue" and @type="button"]'
        self.wait_for_object_by_xpath(continue_xpath)
        button = self.driver.find_element_by_xpath(continue_xpath)
        button.click()

    def set_mode(self, mode, band=None):
        self.add_item_to_command_list(self._set_mode, (mode,), 1, 900)

    def _set_mode(self, mode):
        # Different bands are not supported so we ignore.
        # Create the mode to popup item mapping
        mode_mapping = {self.mode_b: 'B-Only', self.mode_g: 'G-Only',
                        self.mode_b | self.mode_g: 'Mixed'}
        mode_name = ''
        if mode in mode_mapping.keys():
            mode_name = mode_mapping[mode]
        else:
            raise RuntimeError('The mode selected %d is not supported by router'
                               ' %s.', hex(mode), self.get_router_name())
        xpath = ('//select[@onchange="SelWL()" and @name="Mode"]')
        self.select_item_from_popup_by_xpath(mode_name, xpath)

    def set_radio(self, enabled=True):
        # If we are enabling we are activating all other UI components, do it
        # first.  Otherwise we are turning everything off so do it last.
        weight = 1 if enabled else 1000
        self.add_item_to_command_list(self._set_radio, (enabled,), 1, weight)

    def _set_radio(self, enabled=True):
        xpath = ('//select[@onchange="SelWL()" and @name="Mode"]')
        # To turn off we pick disabled, to turn on we set to G
        if not enabled:
            setting = 'Disabled'
        else:
            setting = 'G-Only'
        self.select_item_from_popup_by_xpath(setting, xpath)

    def set_ssid(self, ssid):
        self.add_item_to_command_list(self._set_ssid, (ssid,), 1, 900)

    def _set_ssid(self, ssid):
        self._set_radio(enabled=True)
        xpath = ('//input[@maxlength="32" and @name="SSID"]')
        self.set_content_of_text_field_by_xpath(ssid, xpath)

    def set_channel(self, channel):
        self.add_item_to_command_list(self._set_channel, (channel,), 1, 900)

    def _set_channel(self, channel):
        self._set_radio(enabled=True)
        channel_choices = ['1 - 2.412GHz', '2 - 2.417GHz', '3 - 2.422GHz',
                           '4 - 2.427GHz', '5 - 2.432GHz', '6 - 2.437GHz',
                           '7 - 2.442GHz', '8 - 2.447GHz', '9 - 2.452GHz',
                           '10 - 2.457GHz', '11 - 2.462GHz']
        xpath = ('//select[@onfocus="check_action(this,0)" and @name="Freq"]')
        self.select_item_from_popup_by_xpath(channel_choices[channel - 1],
                                             xpath)

    def set_band(self, band):
        return None

    def set_security_disabled(self):
        self.add_item_to_command_list(self._set_security_disabled, (), 2, 1000)

    def _set_security_disabled(self):
        xpath = ('//select[@name="SecurityMode"]')
        self.select_item_from_popup_by_xpath(self.security_disabled, xpath)

    def set_security_wep(self, key_value, authentication):
        self.add_item_to_command_list(self._set_security_wep,
                                      (key_value, authentication), 2, 1000)

    def _set_security_wep(self, key_value, authentication):
        logging.info('This router %s does not support WEP authentication type:'
                     ' %s', self.get_router_name(), authentication)
        popup = '//select[@name="SecurityMode"]'
        self.wait_for_object_by_xpath(popup)
        text_field = ('//input[@name="wl_passphrase"]')
        self.select_item_from_popup_by_xpath(self.security_wep, popup,
                                             wait_for_xpath=text_field)
        self.set_content_of_text_field_by_xpath(key_value, text_field)
        button = self.driver.find_element_by_xpath('//input[@value="Generate"]')
        button.click()

    def set_security_wpapsk(self, shared_key, update_interval=1800):
        self.add_item_to_command_list(self._set_security_wpapsk,
                                      (shared_key, update_interval), 2, 900)

    def _set_security_wpapsk(self, shared_key, update_interval=1800):
        popup = '//select[@name="SecurityMode"]'
        self.wait_for_object_by_xpath(popup)
        key_field = '//input[@name="PassPhrase"]'
        self.select_item_from_popup_by_xpath(self.security_wpapsk, popup,
                                             wait_for_xpath=key_field)
        self.set_content_of_text_field_by_xpath(shared_key, key_field)
        interval_field = ('//input[@name="GkuInterval"]')
        self.set_content_of_text_field_by_xpath(str(update_interval),
                                                interval_field)

    def set_visibility(self, visible=True):
        self.add_item_to_command_list(self._set_visibility, (visible,), 1, 900)

    def _set_visibility(self, visible=True):
        self._set_radio(enabled=True)
        # value=1 is visible; value=0 is invisible
        int_value = int(visible)
        xpath = ('//input[@value="%d" and @name="wl_closed"]' % int_value)
        element = self.driver.find_element_by_xpath(xpath)
        element.click()
