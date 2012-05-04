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
from selenium.common.exceptions import WebDriverException

class DLinkDIR655APConfigurator(ap_configurator.APConfigurator):
    """Derived class to control the DLink DAP-1522."""

    def __init__(self, router_dict):
        super(DLinkDIR655APConfigurator, self).__init__(router_dict)
        # Overrides
        self.security_disabled = 'None'
        self.security_wep = 'WEP'
        self.security_wpapsk = 'WPA-Personal'
        self.security_wpa2psk = 'WPA-Personal'
        self.security_wpa8021x = 'WPA-Enterprise'
        self.security_wpa28021x = 'WPA2-Enterprise'

    def get_number_of_pages(self):
        return 1

    def get_supported_bands(self):
        return [{'band': self.band_2ghz,
                 'channels': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]}]

    def get_supported_modes(self):
        return [{'band': self.band_2ghz,
                 'modes': [self.mode_b, self.mode_g, self.mode_n,
                           self.mode_b | self.mode_g,
                           self.mode_g | self.mode_n,
                           self.mode_b | self.mode_g | self.mode_n]}]

    def is_security_mode_supported(self, security_mode):
        return security_mode in (self.security_disabled,
                                 self.security_wpapsk,
                                 self.security_wep)

    def navigate_to_page(self, page_number):
        # All settings are on the same page, so we always open the config page
        page_url = urlparse.urljoin(self.admin_interface_url, 'wireless.asp')
        self.driver.get(page_url)
        at_configuration_page = True
        try:
            self.wait_for_object_by_id('w_enable')
        except SeleniumTimeoutException:
            at_configuration_page = False
        if at_configuration_page == False:
            try:
                self.wait_for_object_by_id('log_pass')
            except SeleniumTimeoutException, e:
                raise SeleniumTimeoutException('Unable to navigate to the '
                                               'login or configuration page. '
                                               'WebDriver exception: %s'
                                               % str(e))
            self.set_content_of_text_field_by_id('password', 'log_pass')
            login_button = self.driver.find_element_by_id('login')
            login_button.click()
            # This will send us to the landing page and not where we want to go.
            self.driver.get(page_url)

    def save_page(self, page_number):
        # All settings are on the same page, we can ignore page_number
        button = self.driver.find_element_by_id('button')
        button.click()
        try:
            progress_value = self.wait_for_object_by_id('show_sec')
        except WebDriverException:
            # This may be due to a popup
            alert = self.driver.switch_to_alert()
            alert_text = alert.text
            if alert_text == 'Nothing has changed, save anyway?':
                alert.accept()
            else:
                alert.accept()
                raise RuntimeError('You have entered an invalid configuration: '
                                   '%s' % alert_text)
        # Give the router a minute to update.
        for i in xrange(120):
            progress_value = self.wait_for_object_by_id('show_sec')
            html = self.driver.execute_script('return arguments[0].innerHTML',
                                              progress_value)
            time.sleep(0.5)
            if int(html) == 0:
                break
        button = self.driver.find_element_by_id('button')
        button.click()
        self.wait_for_object_by_id('w_enable')

    def set_mode(self, mode, band=None):
        # Mode overrides the band.  So if a band change is made after a mode
        # change it may make an incompatible pairing.
        self.add_item_to_command_list(self._set_mode, (mode, band), 1, 800)

    def _set_mode(self, mode, band=None):
        # Create the mode to popup item mapping
        mode_mapping = {self.mode_b: '802.11b only',
                        self.mode_g: '802.11g only',
                        self.mode_n: '802.11n only',
                        self.mode_b | self.mode_g: 'Mixed 802.11g and 802.11b',
                        self.mode_n | self.mode_g: 'Mixed 802.11n and 802.11g',
                        self.mode_n | self.mode_g | self.mode_b:
                        'Mixed 802.11n, 802.11g and 802.11b'}
        if mode in mode_mapping.keys():
            popup_value = mode_mapping[mode]
        else:
            raise SeleniumTimeoutException('The mode selected %s is not '
                                           'supported by router %s.' %
                                           (hex(mode), self.get_router_name()))
        # When we change to an N based mode another popup is displayed.  We need
        # to wait for the before proceeding.
        wait_for_xpath = 'id("show_ssid")'
        if mode & self.mode_n == self.mode_n:
            wait_for_xpath = 'id("11n_protection")'
        self.select_item_from_popup_by_id(popup_value, 'dot11_mode',
                                          wait_for_xpath=wait_for_xpath)

    def set_radio(self, enabled=True):
        # If we are enabling we are activating all other UI components, do
        # it first. Otherwise we are turning everything off so do it last.
        if enabled:
            weight = 1
        else:
            weight = 1000
        self.add_item_to_command_list(self._set_radio, (enabled,), 1, weight)

    def _set_radio(self, enabled=True):
        # The radio checkbox for this router always has a value of 1. So we need
        # to use other methods to determine if the radio is on or not. Check if
        # the ssid textfield is disabled.
        ssid = self.driver.find_element_by_id('show_ssid')
        checkbox = self.driver.find_element_by_id('w_enable')
        if ssid.get_attribute('disabled') == 'true':
            radio_enabled = False
        else:
            radio_enabled = True
        if radio_enabled == enabled:
            # Nothing to do
            return
        self.set_check_box_selected_by_id('w_enable', selected=False,
            wait_for_xpath='id("wep_type")')

    def set_ssid(self, ssid):
        # Can be done as long as it is enabled
        self.add_item_to_command_list(self._set_ssid, (ssid,), 1, 900)

    def _set_ssid(self, ssid):
        self._set_radio(enabled=True)
        self.set_content_of_text_field_by_id(ssid, 'show_ssid')

    def set_channel(self, channel):
        self.add_item_to_command_list(self._set_channel, (channel,), 1, 900)

    def _set_channel(self, channel):
        self._set_radio(enabled=True)
        channel_popup = self.driver.find_element_by_id('sel_wlan0_channel')
        if channel_popup.get_attribute('disabled') == 'true':
            self.set_check_box_selected_by_id('auto_channel', selected=False)
        self.select_item_from_popup_by_id(str(channel), 'sel_wlan0_channel')

    def set_band(self, band):
        logging.debug('This router (%s) does not support multiple bands.' %
                      self.get_router_name())

    def set_security_disabled(self):
        self.add_item_to_command_list(self._set_security_disabled, (), 1, 900)

    def _set_security_disabled(self):
        self._set_radio(enabled=True)
        self.select_item_from_popup_by_id(self.security_disabled, 'wep_type')

    def set_security_wep(self, key_value, authentication):
        self.add_item_to_command_list(self._set_security_wep,
                                      (key_value, authentication), 1, 900)

    def _set_security_wep(self, key_value, authentication):
        self._set_radio(enabled=True)
        self.select_item_from_popup_by_id(self.security_wep, 'wep_type',
                                          wait_for_xpath='id("key1")')
        self.select_item_from_popup_by_id(authentication, 'auth_type',
                                          wait_for_xpath='id("key1")')
        self.set_content_of_text_field_by_id(key_value, 'key1')

    def set_security_wpapsk(self, shared_key, update_interval=1800):
        self.add_item_to_command_list(self._set_security_wpapsk,
                                      (shared_key, update_interval), 1, 900)

    def _set_security_wpapsk(self, shared_key, update_interval=1800):
        self._set_radio(enabled=True)
        self.select_item_from_popup_by_id(self.security_wpapsk, 'wep_type',
            wait_for_xpath='id("wlan0_gkey_rekey_time")')
        self.select_item_from_popup_by_id('WPA Only', 'wpa_mode',
            wait_for_xpath='id("wlan0_psk_pass_phrase")')
        self.set_content_of_text_field_by_id(str(update_interval),
                                             'wlan0_gkey_rekey_time')
        self.set_content_of_text_field_by_id(shared_key,
                                             'wlan0_psk_pass_phrase')

    def set_visibility(self, visible=True):
        self.add_item_to_command_list(self._set_visibility, (visible,), 1, 900)

    def _set_visibility(self, visible=True):
        self._set_radio(enabled=True)
        # value=1 is visible; value=0 is invisible
        int_value = 1 if visible else 0
        xpath = ('//input[@value="%d" '
                 'and @name="wlan0_ssid_broadcast"]' % int_value)
        element = self.driver.find_element_by_xpath(xpath)
        element.click()
