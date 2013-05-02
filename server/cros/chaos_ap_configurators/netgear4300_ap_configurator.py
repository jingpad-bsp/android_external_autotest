# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

import netgear_WNDR_dual_band_configurator
from netgear_WNDR_dual_band_configurator import *

class Netgear4300APConfigurator(netgear_WNDR_dual_band_configurator.
                                NetgearDualBandAPConfigurator):
    """Derived class to control Netgear WNDR4300 router."""


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
        elif '40 Mhz and 20 Mhz coexistence' in text:
            alert.accept()
        elif 'WPS is going to become inaccessible' in text:
            alert.accept()
        else:
            super(Netgear4300APConfigurator, self)._alert_handler(alert)


    def get_supported_bands(self):
        return [{'band': self.band_2ghz,
                 'channels': ['Auto', 1, 2, 3, 4, 5, 6, 7, 8, 9 , 10, 11]},
                {'band': self.band_5ghz,
                 'channels': [36, 40, 44, 48, 149, 153, 157, 161]}]


    def get_supported_modes(self):
        return [{'band': self.band_5ghz, 'modes': [self.mode_a, self.mode_n]},
                {'band': self.band_2ghz, 'modes': [self.mode_g, self.mode_n]}]


    def logout_from_previous_netgear(self):
        """Some netgear routers dislike you being logged into another
           one of their kind. So make sure that you are not."""
        print 'Logging out of older router'
        self.click_button_by_id('yes')
        self.navigate_to_page(page_number)


    def navigate_to_page(self, page_number):
         try:
             self.get_url(urlparse.urljoin(self.admin_interface_url,
                          'adv_index.htm'), page_title='WNDR4300')
             self.click_button_by_id('setup_bt')
             self.wait_for_object_by_id('wireless')
             self.click_button_by_id('wireless')
         except Exception as e:
             if os.path.basename(self.driver.current_url) != 'adv_index.htm':
                 raise RuntimeError('Invalid url %s' % self.driver.current_url)
             elif os.path.basename(
                  self.driver.current_url) == 'multi_login.html':
                 self.logout_from_previous_netgear()
         setframe = self.driver.find_element_by_xpath(
                    '//iframe[@name="formframe"]')
         settings = self.driver.switch_to_frame(setframe)
         self.wait_for_object_by_xpath('//input[@name="ssid"]')


    def save_page(self, page_number):
        self.click_button_by_xpath('//input[@name="Apply"]',
                                   alert_handler=self._alert_handler)


    def set_channel(self, channel):
        self.add_item_to_command_list(self._set_channel, (channel,), 1, 900)


    def _set_channel(self, channel):
        position = self._get_channel_popup_position(channel)
        channel_choices = ['Auto', '01', '02', '03', '04', '05', '06', '07',
                           '08', '09', '10', '11']
        xpath = '//select[@name="w_channel"]'
        if self.current_band == self.band_5ghz:
            xpath = '//select[@name="w_channel_an"]'
            channel_choices = ['36', '40', '44', '48', '149', '153',
                               '157', '161']
        self.select_item_from_popup_by_xpath(channel_choices[position], xpath)


    def set_security_wep(self, key_value, authentication):
        # The button name seems to differ in various Netgear routers
        self.add_item_to_command_list(self._set_security_wep,
                                      (key_value, authentication), 1, 900)


    def _set_security_wep(self, key_value, authentication):
        xpath = ('//input[@name="security_type" and @value="WEP" and '
                 '@type="radio"]')
        text_field = '//input[@name="passphraseStr"]'
        button = '//input[@name="Generate"]'
        if self.current_band == self.band_5ghz:
            xpath = '//input[@name="security_type_an" and @value="WEP" and\
                     @type="radio"]'
            text_field = '//input[@name="passphraseStr_an"]'
            button = '//input[@name="Generate_an"]'
        try:
            self.wait_for_object_by_xpath(xpath)
            self.click_button_by_xpath(xpath, alert_handler=self._alert_handler)
        except Exception, e:
            raise RuntimeError('We got an exception: "%s". Check the mode. '
                               'It should be \'Up to 54 Mbps\'.' % str(e))
        self.wait_for_object_by_xpath(text_field)
        self.set_content_of_text_field_by_xpath(key_value, text_field,
                                                abort_check=True)
        self.click_button_by_xpath(button, alert_handler=self._alert_handler)
