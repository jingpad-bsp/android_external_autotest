# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import urlparse

import linksyse_dual_band_configurator

class Linksyse2500APConfigurator(linksyse_dual_band_configurator.
                                 LinksyseDualBandAPConfigurator):
    """Derived class to control Linksys E2500 router."""


    def _sec_alert(self, alert):
        text = alert.text
        if 'Your wireless security mode is not compatible with' in text:
            alert.accept()
        elif 'WARNING: Your Wireless-N devices will only operate' in text:
            alert.accept()
        else:
            alert.accept()
            raise RuntimeError('We have an unhandled alert: %s' % text)


    def get_number_of_pages(self):
        return 2


    def get_supported_modes(self):
        return [{'band': self.band_2ghz,
                 'modes': [self.mode_b, self.mode_n, self.mode_b |
                           self.mode_g, self.mode_g, self.mode_m]},
                {'band': self.band_5ghz,
                 'modes': [self.mode_a, self.mode_n, self.mode_m]}]


    def is_security_mode_supported(self, security_mode):
        if self.current_band == self.band_5ghz:
            return security_mode in (self.security_type_disabled,
                                     self.security_type_wpapsk,
                                     self.security_type_wpa2psk)
        return security_mode in (self.security_type_disabled,
                                 self.security_type_wpapsk,
                                 self.security_type_wpa2psk,
                                 self.security_type_wep)


    def navigate_to_page(self, page_number):
        if page_number == 1:
            page_url = urlparse.urljoin(self.admin_interface_url,
                                        'Wireless_Basic.asp')
            self.get_url(page_url, page_title='Settings')
        elif page_number == 2:
            page_url = urlparse.urljoin(self.admin_interface_url,
                                        'WL_WPATable.asp')
            self.get_url(page_url, page_title='Security')
        else:
            raise RuntimeError('Invalid page number passed. Number of pages '
                               '%d, page value sent was %d' %
                               (self.get_number_of_pages(), page_number))


    def _set_mode(self, mode, band=None):
        mode_mapping = {self.mode_b: 'Wireless-B Only',
                        self.mode_g: 'Wireless-G Only',
                        self.mode_b | self.mode_g: 'Wireless-B/G Only',
                        self.mode_n: 'Wireless-N Only',
                        self.mode_a: 'Wireless-A Only',
                        self.mode_m: 'Mixed'}
        xpath = '//select[@name="net_mode_24g"]'
        if self.current_band == self.band_5ghz or band == self.band_5ghz:
            self.current_band = self.band_5ghz
            xpath = '//select[@name="net_mode_5g"]'
        mode_name = ''
        if mode in mode_mapping.keys():
            mode_name = mode_mapping[mode]
            if (mode & self.mode_a) and (self.current_band != self.band_5ghz):
                #  a mode only in 5Ghz
                logging.debug('Mode \'a\' is not available for 2.4Ghz band.')
                return
            elif ((mode & (self.mode_b | self.mode_g) ==
                  (self.mode_b | self.mode_g)) or
                 (mode & self.mode_b == self.mode_b) or
                 (mode & self.mode_g == self.mode_g)) and \
                 (self.current_band != self.band_2ghz):
                #  b/g, b, g mode only in 2.4Ghz
                logging.debug('Mode \'%s\' is not available for 5Ghz band.',
                              mode_name)
                return
        else:
            raise RuntimeError('The mode selected %d is not supported by router'
                               ' %s.', hex(mode), self.get_router_name())
        self.select_item_from_popup_by_xpath(mode_name, xpath)


    def _set_ssid(self, ssid):
        xpath = '//input[@maxlength="32" and @name="ssid_24g"]'
        if self.current_band == self.band_5ghz:
            xpath = '//input[@maxlength="32" and @name="ssid_5g"]'
        self.set_content_of_text_field_by_xpath(ssid, xpath)


    def _set_channel(self, channel):
        position = self._get_channel_popup_position(channel)
        channel_choices = ['Auto',
                           '1 - 2.412GHZ', '2 - 2.417GHZ', '3 - 2.422GHZ',
                           '4 - 2.427GHZ', '5 - 2.432GHZ', '6 - 2.437GHZ',
                           '7 - 2.442GHZ', '8 - 2.447GHZ', '9 - 2.452GHZ',
                           '10 - 2.457GHZ', '11 - 2.462GHZ']
        xpath = '//select[@name="_wl0_channel"]'
        if self.current_band == self.band_5ghz:
            xpath = '//select[@name="_wl1_channel"]'
            channel_choices = ['Auto (DFS)',
                               '36 - 5.180GHz', '40 - 5.200GHz',
                               '44 - 5.220GHz', '48 - 5.240GHz',
                               '149 - 5.745GHz', '153 - 5.765GHz',
                               '157 - 5.785GHz', '161 - 5.805GHz']
        self.select_item_from_popup_by_xpath(channel_choices[position],
                                             xpath)


    def set_security_disabled(self):
        self.add_item_to_command_list(self._set_security_disabled, (), 2, 900)


    def set_security_wep(self, key_value, authentication):
        self.add_item_to_command_list(self._set_security_wep,
                                      (key_value, authentication), 2, 900)


    def set_security_wpapsk(self, shared_key, update_interval=None):
        self.add_item_to_command_list(self._set_security_wpapsk,
                                      (shared_key, update_interval), 2, 900)


    def _set_visibility(self, visible=True):
        button = 'closed_24g'
        if self.current_band == self.band_5ghz:
            button = 'closed_5g'
        int_value = 0 if visible else 1
        xpath = ('//input[@value="%d" and @name="%s"]' % (int_value, button))
        self.click_button_by_xpath(xpath)
