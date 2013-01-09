# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import asus_ap_configurator


class AsusQISAPConfigurator(asus_ap_configurator.AsusAPConfigurator):
    """Derived class for Asus routers with the Quick Internet Setup UI."""

    def __init__(self, router_dict):
        super(AsusQISAPConfigurator, self).__init__(router_dict)
        self.mode_n = 'N Only'
        self.mode_legacy = 'Legacy'
        self.mode_auto = 'auto'


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
        try:
            self.driver.get('%s/Advanced_Wireless_Content.asp' %
                            self.admin_interface_url)
        except Exception, e:
            raise RuntimeError('Could not load the page, Error: %s' % str(e))


    def get_number_of_pages(self):
        return 1


    def save_page(self, page_number):
        self.click_button_by_id('applyButton')
        ssid = '//input[@name="wl_ssid"]'
        try:
            self.wait_for_object_by_xpath(ssid)
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
                 'modes': [self.mode_legacy, self.mode_n, self.mode_auto]},
                {'band': self.band_5ghz,
                 'modes': [self.mode_legacy, self.mode_n, self.mode_auto]}]


    def _set_mode(self, mode, band=None):
        if band:
            self._set_band(band)
        xpath = '//select[@name="wl_nmode_x"]'
        self.select_item_from_popup_by_xpath(mode, xpath,
             alert_handler=self._invalid_security_handler)


    def _set_ssid(self, ssid):
        xpath = '//input[@maxlength="32" and @name="wl_ssid"]'
        self.set_content_of_text_field_by_xpath(ssid, xpath)


    def _set_channel(self, channel):
        position = self._get_channel_popup_position(channel)
        channel_choices = ['Auto', '01', '02', '03', '04', '05', '06',
                           '07', '08', '09', '10', '11']
        xpath = '//select[@name="wl_channel"]'
        if self.current_band == self.band_5ghz:
            channel_choices = ['Auto', '36', '40', '44', '48', '149', '153',
                               '157', '161']
        self.select_item_from_popup_by_xpath(str(channel_choices[position]),
                                             xpath)


    def _set_band(self, band):
        xpath = '//select[@name="wl_unit"]'
        self.select_item_from_popup_by_xpath(band, xpath)


    def _set_security_disabled(self):
        self._set_authentication(self.wep_authentication_open)


    def _set_security_wep(self, key_value, authentication):
        popup = '//select[@name="wl_wep_x"]'
        text_field = '//input[@name="wl_phrase_x"]'
        self._set_authentication(self.wep_authentication_shared,
                                 wait_for_xpath=popup)
        self.select_item_from_popup_by_xpath(self.security_wep64, popup,
                                             wait_for_xpath=text_field,
                           alert_handler=self._invalid_security_handler)
        self.set_content_of_text_field_by_xpath(key_value, text_field,
                                                abort_check=True)


    def _set_security_wpa2psk(self, shared_key, update_interval):
        popup = '//select[@name="wl_crypto"]'
        key_field = '//input[@name="wl_wpa_psk"]'
        interval_field = '//input[@name="wl_wpa_gtk_rekey"]'
        self._set_authentication(self.security_wpapsk,
                                 wait_for_xpath=key_field)
        self.select_item_from_popup_by_xpath('TKIP', popup)
        self.set_content_of_text_field_by_xpath(shared_key, key_field)
        self.set_content_of_text_field_by_xpath(str(update_interval),
                                                interval_field)


    def _set_visibility(self, visible=True):
        value = 0 if visible else 1
        xpath = '//input[@name="wl_closed" and @value="%s"]' % value
        self.click_button_by_xpath(xpath)
