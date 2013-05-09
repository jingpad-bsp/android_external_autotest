# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Class to control the Asus QIS router."""

import asus_ap_configurator


class AsusQISAPConfigurator(asus_ap_configurator.AsusAPConfigurator):
    """Derived class for Asus routers with the Quick Internet Setup UI."""


    def _set_authentication(self, authentication, wait_for_xpath=None):
        """Sets the authentication method in the popup.

        Args:
          authentication: The authentication method to select.
          wait_for_path: An item to wait for before returning.
        """
        auth = '//select[@name="wl_auth_mode_x"]'
        self.select_item_from_popup_by_xpath(authentication, auth,
            wait_for_xpath, alert_handler=self._invalid_security_handler)


    def navigate_to_page(self, page_number):
        self.get_url('%s/Advanced_Wireless_Content.asp' %
                         self.admin_interface_url, page_title='General')


    def get_number_of_pages(self):
        return 1


    def save_page(self, page_number):
        self.click_button_by_id('applyButton')
        ssid = '//input[@name="wl_ssid"]'
        try:
            self.wait_for_objects_by_xpath([ssid])
        except selenium.common.exceptions.TimeoutException, e:
            raise RuntimeError('Unable to find the object by xpath: %s\n '
                               'WebDriver exception: %s' % (ssid, str(e)))


    def get_supported_bands(self):
        return [{'band': self.band_2ghz,
                 'channels': ['Auto', 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]},
                {'band': self.band_5ghz,
                 'channels': ['Auto', 36, 40, 44, 48, 149, 153, 157, 161]}]


    def get_supported_modes(self):
        return [{'band': self.band_2ghz,
                 'modes': [self.mode_n, self.mode_auto]},
                {'band': self.band_5ghz,
                 'modes': [self.mode_n, self.mode_auto]}]


    def set_mode(self, mode, band=None):
        # To avoid the modal dialog.
        self.add_item_to_command_list(self._set_security_disabled, (), 1, 799)
        self.add_item_to_command_list(self._set_mode, (mode, band), 1, 800)


    def _set_mode(self, mode, band=None):
        if band:
            self._set_band(band)
        if mode == self.mode_auto:
            mode_popup = 'auto'
        elif mode == self.mode_n:
            mode_popup = 'N Only'
        else:
            raise RuntimeError('Invalid mode passed %x' % mode)
        xpath = '//select[@name="wl_nmode_x"]'
        self.select_item_from_popup_by_xpath(mode_popup, xpath,
             alert_handler=self._invalid_security_handler)


    def set_ssid(self, ssid):
        self.add_item_to_command_list(self._set_ssid, (ssid,), 1, 900)


    def _set_ssid(self, ssid):
        xpath = '//input[@maxlength="32" and @name="wl_ssid"]'
        self.set_content_of_text_field_by_xpath(ssid, xpath)


    def set_channel(self, channel):
        self.add_item_to_command_list(self._set_channel, (channel,), 1, 900)


    def _set_channel(self, channel):
        position = self._get_channel_popup_position(channel)
        channel_choices = ['Auto', '1', '2', '3', '4', '5', '6',
                           '7', '8', '9', '10', '11']
        xpath = '//select[@name="wl_channel"]'
        if self.current_band == self.band_5ghz:
            channel_choices = ['Auto', '36', '40', '44', '48', '149', '153',
                               '157', '161']
        self.select_item_from_popup_by_xpath(str(channel_choices[position]),
                                             xpath)


    def set_band(self, band):
        if band == self.band_2ghz:
            self.current_band = self.band_2ghz
        elif band == self.band_5ghz:
            self.current_band = self.band_5ghz
        else:
            raise RuntimeError('Invalid band sent %s' % band)
        self.add_item_to_command_list(self._set_band, (band,), 1, 800)


    def _set_band(self, band):
        xpath = '//select[@name="wl_unit"]'
        self.select_item_from_popup_by_xpath(band, xpath)


    def set_security_disabled(self):
        self.add_item_to_command_list(self._set_security_disabled, (), 1, 1000)


    def _set_security_disabled(self):
        self._set_authentication('Open System')


    def set_security_wep(self, key_value, authentication):
        self.add_item_to_command_list(self._set_security_wep,
                                      (key_value, authentication), 1, 1000)


    def _set_security_wep(self, key_value, authentication):
        popup = '//select[@name="wl_wep_x"]'
        text_field = '//input[@name="wl_phrase_x"]'
        self._set_authentication('Shared Key', wait_for_xpath=popup)
        self.select_item_from_popup_by_xpath('WEP-64bits', popup,
                                             wait_for_xpath=text_field,
                           alert_handler=self._invalid_security_handler)
        self.set_content_of_text_field_by_xpath(key_value, text_field,
                                                abort_check=True)

    def set_security_wpapsk(self, shared_key, update_interval=1800):
        #  Asus does not support TKIP (wpapsk) encryption in 'n' mode.
        #  So we will use AES (wpa2psk) to avoid conflicts and modal dialogs.
        self.add_item_to_command_list(self._set_security_wpapsk,
                                      (shared_key, update_interval), 1, 1000)


    def _set_security_wpapsk(self, shared_key, update_interval):
        popup = '//select[@name="wl_crypto"]'
        key_field = '//input[@name="wl_wpa_psk"]'
        interval_field = '//input[@name="wl_wpa_gtk_rekey"]'
        self._set_authentication('WPA-Personal', wait_for_xpath=key_field)
        self.select_item_from_popup_by_xpath('TKIP', popup)
        self.set_content_of_text_field_by_xpath(shared_key, key_field)
        self.set_content_of_text_field_by_xpath(str(update_interval),
                                                interval_field)


    def set_visibility(self, visible=True):
        self.add_item_to_command_list(self._set_visibility,(visible,), 1, 900)


    def _set_visibility(self, visible=True):
        value = 0 if visible else 1
        xpath = '//input[@name="wl_closed" and @value="%s"]' % value
        self.click_button_by_xpath(xpath)
