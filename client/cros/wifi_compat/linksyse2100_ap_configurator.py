# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import linksyse_single_band_configurator


class linksyse2100APConfigurator(linksyse_single_band_configurator.
                                 linksyse_single_bandAPConfigurator):
    """Derived class to control Linksys E2100 router."""


    def _set_mode(self, mode, band=None):
        mode_mapping = {self.mode_m:'Mixed',
                        self.mode_b | self.mode_g:'BG-Mixed',
                        self.mode_g:'Wireless-G Only',
                        self.mode_b:'Wireless-B Only',
                        self.mode_n:'Wireless-N Only'}
        mode_name = mode_mapping.get(mode)
        if not mode_name:
            raise RuntimeError('The mode %d not supported by router %s. ',
                               hex(mode), self.get_router_name())
        xpath = '//select[@name="wl_net_mode"]'
        self.select_item_from_popup_by_xpath(mode_name, xpath,
                                             alert_handler=self._sec_alert)


    def _set_ssid(self, ssid):
        xpath = '//input[@maxlength="32" and @name="wl_ssid"]'
        self.set_content_of_text_field_by_xpath(ssid, xpath, abort_check=False)


    def _set_channel(self, channel):
        xpath = '//select[@name="wl_schannel"]'
        channels = ['1 - 2.412 GHz', '2 - 2.417 GHz', '3 - 2.422 GHz',
                    '4 - 2.427 GHz', '5 - 2.432 GHz', '6 - 2.437 GHz',
                    '7 - 2.442 GHz', '8 - 2.447 GHz', '9 - 2.452 GHz',
                    '10 - 2.457 GHz', '11 - 2.462 GHz']
        self.select_item_from_popup_by_xpath(channels[channel], xpath)


    def _set_ch_width(self, channel_wid):
        channel_width_choice = ['Auto', 'Standard - 20MHz Channel']
        xpath = '//select[@name="_wl_nbw"]'
        self.select_item_from_popup_by_xpath(channel_width_choice[channel_wid],
                                             xpath)


    def _set_security_disabled(self):
        xpath = '//select[@name="security_mode2"]'
        self.select_item_from_popup_by_xpath(self.security_disabled, xpath)


    def _set_security_wep(self, key_value, authentication):
        # WEP and WPA-Personal are not supported for Wireless-N only mode
        # and Mixed mode.
        # WEP and WPA-Personal do not show up in the list, no alert is thrown.
        popup = '//select[@name="security_mode2"]'
        self.select_item_from_popup_by_xpath(self.security_wep, popup,
                                             alert_handler=self._sec_alert)
        text = '//input[@name="wl_passphrase"]'
        self.set_content_of_text_field_by_xpath(key_value, text,
                                                abort_check=False)
        xpath = '//input[@value="Generate"]'
        self.click_button_by_xpath(xpath, alert_handler=self._sec_alert)


    def _set_security_wpa2psk(self, shared_key):
        popup = '//select[@name="security_mode2"]'
        self.select_item_from_popup_by_xpath(self.security_wpa2psk, popup,
                                             alert_handler=self._sec_alert)
        text = '//input[@name="wl_wpa_psk"]'
        self.set_content_of_text_field_by_xpath(shared_key, text,
                                                abort_check=False)
