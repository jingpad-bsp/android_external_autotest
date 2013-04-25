# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import netgear_WNDR_dual_band_configurator
import logging


class NetgearR6200APConfigurator(netgear_WNDR_dual_band_configurator.
                                NetgearDualBandAPConfigurator):
    """Derived class to control Netgear R6200 router."""


    def _alert_handler(self, alert):
        """Checks for any modal dialogs which popup to alert the user and
        either raises a RuntimeError or ignores the alert.

        @params alert: The modal dialog's contents.
        """
        text = alert.text
        if 'WPS requires SSID broadcasting in order to work' in text:
            alert.accept()
        else:
            super(NetgearR6200APConfigurator, self)._alert_handler(alert)


    def get_supported_modes(self):
        return [{'band': self.band_2ghz, 'modes': [self.mode_b, self.mode_g,
                                                   self.mode_n]},
                {'band': self.band_5ghz, 'modes': [self.mode_g, self.mode_a,
                                                   self.mode_n]}]


    def get_supported_bands(self):
        return [{'band': self.band_2ghz,
                 'channels': ['Auto', 1, 2, 3, 4, 5, 6, 7, 8, 9 , 10, 11]},
                {'band': self.band_5ghz,
                 'channels': [36, 40, 44, 48, 149, 153, 157, 161]}]


    def is_security_mode_supported(self, security_mode):
        return security_mode in (self.security_type_disabled,
                                 self.security_type_wpa2psk,
                                 self.security_type_wep)


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
        self.select_item_from_popup_by_xpath(channel_choices[position],
                                             xpath)


    def _set_mode(self, mode, band=None):
        router_mode = None
        xpath = '//select[@name="opmode"]'
        if self.current_band == self.band_2ghz:
            if mode == self.mode_b:
                router_mode = 'Up to 54 Mbps'
            elif mode == self.mode_g:
                router_mode = 'Up to 145 Mbps'
            elif mode == self.mode_n:
                router_mode = 'Up to 300 Mbps'
        elif self.current_band == self.band_5ghz:
            xpath = '//select[@name="opmode_an"]'
            if mode == self.mode_g:
                router_mode = 'Up to 173 Mbps'
            elif mode == self.mode_a:
                router_mode = 'Up to 400 Mbps'
            elif mode == self.mode_n:
                router_mode = 'Up to 867 Mbps'
        if not router_mode:
            raise RuntimeException('You selected a mode that is not assigned '
                                   'to this router. Select either b, g or n '
                                   'for 2.4Ghz or either g, a or n for 5Ghz.')
        self.select_item_from_popup_by_xpath(router_mode, xpath)


    def set_security_wep(self, key_value, authentication):
        if self.current_band == self.band_5ghz:
            logging.debug('Cannot set WEP security for 5GHz band in Netgear '
                          'R6200 router.')
            return None
        super(NetgearR6200APConfigurator, self).set_security_wep(
        key_value, authentication)

