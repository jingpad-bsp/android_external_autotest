# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import urlparse

import ap_configurator

from selenium.common.exceptions import WebDriverException


class LinksyseSingleBandAPConfigurator(ap_configurator.APConfigurator):
    """Base class for objects to configure Linksys single band access points
       using webdriver."""


    def __init__(self, router_dict):
        super(LinksyseSingleBandAPConfigurator, self).__init__(router_dict)
        self.security_disabled = 'Disabled'
        self.security_wep = 'WEP'
        self.security_wpapsk = 'WPA Personal'
        self.security_wpa2psk = 'WPA2 Personal'
        self.security_wpa8021x = 'WPA Enterprise'
        self.security_wpa28021x = 'WPA2 Enterprise'
        self.mode_m = 0x1001


    def _sec_alert(self, alert):
        text = alert.text
        if 'Your wireless security mode is not compatible with' in text:
            alert.accept()
        elif 'WARNING: Your Wireless-N devices will only operate' in text:
            alert.accept()
        elif 'Wireless security is currently disabled.' in text:
            alert.accept()
            self.click_button_by_xpath('//a[text()="Save Settings"]',
                                       alert_handler=self._sec_alert)
        elif 'Your new setting will disable Wi-Fi Protected Setup.' in text:
            alert.accept()
        else:
           raise RuntimeError('Invalid handler')


    def get_number_of_pages(self):
        return 2


    def get_supported_modes(self):
        return [{'band': self.band_2ghz,
                 'modes': [self.mode_m, self.mode_b | self.mode_g, self.mode_g,
                           self.mode_b, self.mode_n]}]


    def get_supported_bands(self):
        return [{'band': self.band_2ghz,
                 'channels': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]}]


    def is_security_mode_supported(self, security_mode):
        return security_mode in (self.security_disabled,
                                 self.security_wpa8021x,
                                 self.security_wpapsk,
                                 self.security_wpa2psk,
                                 self.security_wep,
                                 self.security_wpa28021x)


    def navigate_to_page(self, page_number):
        if page_number == 1:
            page_url = urlparse.urljoin(self.admin_interface_url,
                                        'Wireless_Basic.asp')
            self.driver.get(page_url)
        elif page_number == 2:
            page_url = urlparse.urljoin(self.admin_interface_url,
                                        'WL_WPATable.asp')
            self.driver.get(page_url)
        else:
            raise RuntimeError('Invalid page number passed. Number of pages '
                               '%d, page value sent was %d' %
                               (self.get_number_of_pages(), page_number))


    def save_page(self, page_number):
        try:
            self.driver.find_element_by_xpath('//a[text()="Save Settings"]')
            return
        except WebDriverException, e:
            message = str(e)
            if message.find('An open modal dialog blocked the operation') == -1:
                return
        alert = self.driver.switch_to_alert()
        alert_text = alert.text
        alert.accept()
        self.click_button_by_xpath('//a[text()="Save Settings"]',
                                   alert_handler=self._sec_alert)
        button_xpath = '//input[@name="action"]'
        if self.wait_for_object_by_xpath(button_xpath):
            self.click_button_by_xpath(button_xpath)


    def set_mode(self, mode, band=None):
        self.add_item_to_command_list(self._set_mode, (mode,), 1, 900)


    def _set_mode(self, mode, band=None):
        mode_mapping = {self.mode_m:'Mixed',
                        self.mode_b | self.mode_g:'Wireless-B/G Only',
                        self.mode_g:'Wireless-G Only',
                        self.mode_b:'Wireless-B Only',
                        self.mode_n:'Wireless-N Only'}
        mode_name = mode_mapping.get(mode)
        if not mode_name:
            raise RuntimeError('The mode %d not supported by router %s. ',
                               hex(mode), self.get_router_name())
        xpath = '//select[@name="net_mode_24g"]'
        self.select_item_from_popup_by_xpath(mode_name, xpath,
                                             alert_handler=self._sec_alert)


    def set_ssid(self, ssid):
        self.add_item_to_command_list(self._set_ssid, (ssid,), 1, 900)


    def _set_ssid(self, ssid):
        xpath = '//input[@maxlength="32" and @name="ssid_24g"]'
        self.set_content_of_text_field_by_xpath(ssid, xpath, abort_check=False)


    def set_channel(self, channel):
        self.add_item_to_command_list(self._set_channel, (channel,), 1, 900)


    def _set_channel(self, channel):
        position = self._get_channel_popup_position(channel)
        xpath = '//select[@name="_wl0_channel"]'
        channels = ['1 - 2.412 GHz', '2 - 2.417 GHz', '3 - 2.422 GHz',
                    '4 - 2.427 GHz', '5 - 2.432 GHz', '6 - 2.437 GHz',
                    '7 - 2.442 GHz', '8 - 2.447 GHz', '9 - 2.452 GHz',
                    '10 - 2.457 GHz', '11 - 2.462 GHz']
        self.select_item_from_popup_by_xpath(channels[position], xpath)


    def set_channel_width(self, channel_wid):
        self.add_item_to_command_list(self._set_channel_width,(channel_wid,),
                                      1, 900)


    def _set_channel_width(self, channel_wid):
        channel_width_choice = ['Auto (20 MHz or 40 MHz)', '20 MHz Only']
        xpath = '//select[@name="_wl0_nbw"]'
        self.select_item_from_popup_by_xpath(channel_width_choice[channel_wid],
                                             xpath)


    def set_radio(self, enabled=True):
        logging.info('set_radio is not supported in Linksys single band AP.')
        return None


    def set_band(self, enabled=True):
        logging.info('set_band is not supported in Linksys single band AP.')
        return None


    def set_security_disabled(self):
        self.add_item_to_command_list(self._set_security_disabled, (), 2, 1000)


    def _set_security_disabled(self):
        xpath = '//select[@name="wl0_security_mode"]'
        self.select_item_from_popup_by_xpath(self.security_disabled, xpath,
                                             alert_handler=self._sec_alert)


    def set_security_wep(self, key_value, authentication):
        self.add_item_to_command_list(self._set_security_wep,
                                      (key_value, authentication), 2, 1000)


    def _set_security_wep(self, key_value, authentication):
        # WEP and WPA-Personal are not supported for Wireless-N only mode
        # and Mixed mode.
        # WEP and WPA-Personal do not show up in the list, no alert is thrown.
        popup = '//select[@name="wl0_security_mode"]'
        self.select_item_from_popup_by_xpath(self.security_wep, popup,
                                             alert_handler=self._sec_alert)
        text = '//input[@name="wl0_passphrase"]'
        self.set_content_of_text_field_by_xpath(key_value, text,
                                                abort_check=True)
        xpath = '//input[@value="Generate"]'
        self.click_button_by_xpath(xpath, alert_handler=self._sec_alert)


    def set_security_wpapsk(self, shared_key):
        # WEP and WPA-Personal are not supported for Wireless-N only mode,
        # so use WPA2-Personal to avoid conflicts.
        self.add_item_to_command_list(self._set_security_wpa2psk,
                                      (shared_key,), 2, 900)


    def _set_security_wpa2psk(self, shared_key):
        popup = '//select[@name="wl0_security_mode"]'
        self.select_item_from_popup_by_xpath(self.security_wpa2psk, popup,
                                             alert_handler=self._sec_alert)
        text = '//input[@name="wl0_wpa_psk"]'
        self.set_content_of_text_field_by_xpath(shared_key, text,
                                                abort_check=False)


    def set_visibility(self, visible=True):
        logging.info('Visibility is not supported for Linksys single band AP')
        return None
