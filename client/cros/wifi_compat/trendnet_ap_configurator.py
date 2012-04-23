# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import time

import ap_configurator
import selenium
import selenium.common.exceptions
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait


class TrendnetAPConfigurator(ap_configurator.APConfigurator):
    """Derived class to control the Trendnet TEW-639GR."""

    def __init__(self, admin_interface_url):
        super(TrendnetAPConfigurator, self).__init__()
        # Overrides
        self.security_disabled = 'Disable'
        self.security_wpapsk = 'WPA2-PSK'

        self.admin_interface_url = admin_interface_url

    def get_router_name(self):
        return 'Router Name: TEW-639GR; Class: TrendnetAPConfigurator'

    def get_router_short_name(self):
        return 'TEW-639GR'

    def get_number_of_pages(self):
        return 2

    def get_supported_bands(self):
        return [{'band': self.band_2ghz,
                 'channels': range(1, 12)}]

    def get_supported_modes(self):
        return [{'band': self.band_2ghz,
                 'modes': [self.mode_n,
                           self.mode_b | self.mode_g,
                           self.mode_b | self.mode_g | self.mode_n]}]

    def is_security_mode_supported(self, security_mode):
        return security_mode in (self.security_disabled, self.security_wpapsk)

    def navigate_to_page(self, page_number):
        # All settings are on the same page, so we always open the config page
        if page_number == 1:
            self.driver.get('http://%s/wireless/basic.asp' %
                            self.admin_interface_url)
        elif page_number == 2:
            self.driver.get('http://%s/wireless/security.asp' %
                            self.admin_interface_url)
        else:
            raise RuntimeError('Invalid page number passed.  Number of pages '
                               '%d, page value sent was %d' %
                               (self.get_number_of_pages(), page_number))

    def save_page(self, page_number):
        if page_number == 1:
            xpath = ('//input[@type="submit" and @value="Apply"]')
        elif page_number == 2:
            xpath = ('//input[@class="button_submit" and @value="Apply"]')
        button = self.driver.find_element_by_xpath(xpath)
        button.click()
        self.wait = WebDriverWait(self.driver, timeout=60)
        xpath = ('//input[@value="Reboot the Device"]')
        button = self.wait_for_object_by_xpath(xpath)
        button.click()
        self.wait = WebDriverWait(self.driver, timeout=5)
        # Give the trendnet up to 2 minutes.  The idea here is to end when the
        # reboot is complete.
        for i in xrange(240):
            progress_value = self.wait_for_object_by_id('progressValue')
            html = self.driver.execute_script('return arguments[0].innerHTML',
                                              progress_value)
            percentage = html.rstrip('%')
            if int(percentage) < 95:
                time.sleep(0.5)
            else:
                return

    def set_mode(self, mode, band=None):
        self.add_item_to_command_list(self._set_mode, (mode,), 1, 100)

    def _set_mode(self, mode, band=None):
        # Different bands are not supported so we ignore.
        # Create the mode to popup item mapping
        mode_mapping = {self.mode_b | self.mode_g | self.mode_n:
                        '2.4GHz 802.11 b/g/n mixed mode',
                        self.mode_n: '2.4GHz 802.11 n only',
                        self.mode_b | self.mode_g:
                        '2.4GHz 802.11 b/g mixed mode'}
        mode_name = ''
        if mode in mode_mapping.keys():
            mode_name = mode_mapping[mode]
        else:
            raise RuntimeError('The mode selected %d is not supported by router'
                               ' %s.', hex(mode), self.get_router_name())
        self.select_item_from_popup_by_id(mode_name, 'wirelessmode',
                                          wait_for_xpath='id("wds_mode")')

    def set_radio(self, enabled=True):
        self.add_item_to_command_list(self._set_radio, (enabled,), 1, 100)

    def _set_radio(self, enabled=True):
        logging.info('Enabling/Disabling the radio is not supported on this '
                     'router (%s).  Setting SSID visibility to %s.' %
                     (self.get_router_name(), bool(enabled)))
        self._set_visibility(visible=enabled)

    def set_ssid(self, ssid):
        self.add_item_to_command_list(self._set_ssid, (ssid,), 1, 100)

    def _set_ssid(self, ssid):
        self.set_content_of_text_field_by_id(ssid, 'display_SSID1')

    def set_channel(self, channel):
        self.add_item_to_command_list(self._set_channel, (channel,), 1, 100)

    def _set_channel(self, channel):
        channel_choices = ['2412MHz (Channel 1)', '2417MHz (Channel 2)',
                           '2422MHz (Channel 3)', '2427MHz (Channel 4)',
                           '2432MHz (Channel 5)', '2437MHz (Channel 6)',
                           '2442MHz (Channel 7)', '2447MHz (Channel 8)',
                           '2452MHz (Channel 9)', '2457MHz (Channel 10)',
                           '2462MHz (Channel 11)']
        self.select_item_from_popup_by_id(channel_choices[channel - 1],
                                          'sz11gChannel')

    def set_band(self, band):
        return None

    def set_security_disabled(self):
        self.add_item_to_command_list(self._set_security_disabled, (), 2, 1000)

    def _set_security_disabled(self):
        self.wait_for_object_by_id('security_mode')
        self.select_item_from_popup_by_id(self.security_disabled,
                                          'security_mode')

    def set_security_wep(self, key_value, authentication):
        logging.info('This router %s does not support wep authentication' %
                     self.get_router_name)

    def set_security_wpapsk(self, shared_key, update_interval=1800):
        self.add_item_to_command_list(self._set_security_wpapsk,
                                      (shared_key, update_interval), 2, 900)

    def _set_security_wpapsk(self, shared_key, update_interval=1800):
        self.wait_for_object_by_id('security_mode')
        self.select_item_from_popup_by_id(self.security_wpapsk,
                                          'security_mode',
                                          wait_for_xpath='id("passphrase")')
        self.set_content_of_text_field_by_id(shared_key, 'passphrase')
        self.set_content_of_text_field_by_id(update_interval,
                                             'keyRenewalInterval')

    def set_visibility(self, visible=True):
        self.add_item_to_command_list(self._set_visibility, (visible,), 1, 100)

    def _set_visibility(self, visible=True):
        # value=1 is visible; value=0 is invisible
        int_value = int(visible)
        xpath = ('//input[@value="%d" and @name="broadcastssid"]' % int_value)
        self.wait_for_object_by_xpath(xpath)
        element = self.driver.find_element_by_xpath(xpath)
        element.click()
