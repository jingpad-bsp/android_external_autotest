# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import urlparse

import ap_configurator


class NetgearDualBandAPConfigurator(ap_configurator.APConfigurator):
    """Base class for Netgear WNDR dual band routers."""


    def __init__(self, ap_config=None):
        super(NetgearDualBandAPConfigurator, self).__init__(
              ap_config=ap_config)
        self.mode_54 = 'Up to 54 Mbps'
        self.mode_217 = 'Up to 217 Mbps'
        self.mode_450 = 'Up to 450 Mbps'
        self.mode_130 = 'Up to 130 Mbps'
        self.mode_300 = 'Up to 300 Mbps'


    def _alert_handler(self, alert):
        """Checks for any modal dialogs which popup to alert the user and
        either raises a RuntimeError or ignores the alert.

        Args:
          alert: The modal dialog's contents.
        """
        text = alert.text
        if 'WPA-PSK [TKIP] ONLY operates at \"Up to 54Mbps\"' in text:
            alert.accept()
            raise RuntimeError('Wrong mode selected. %s' % text)
        elif '2.4G and 5G have the same SSID' in text:
            alert.accept()
            raise RuntimeError('%s. Please change the SSID of one band' % text)
        elif 'do not want any wireless security on your network?' in text:
            alert.accept()
        elif 'recommends that you set the router to a high channel' in text:
            alert.accept()
        else:
            raise RuntimeError('We have an unhandled alert: %s' % text)


    def get_number_of_pages(self):
        return 1


    def get_supported_bands(self):
        return [{'band': self.band_2ghz,
                 'channels': ['Auto', 1, 2, 3, 4, 5, 6, 7, 8, 9 , 10, 11]},
                {'band': self.band_5ghz,
                 'channels': ['Auto', 36, 40, 44, 48, 149, 153,
                              157, 161, 165]}]


    def get_supported_modes(self):
        mode_2Ghz = mode_5Ghz = [self.mode_217, self.mode_450, self.mode_54]
        return [{'band': self.band_5ghz, 'modes': mode_5Ghz},
                {'band': self.band_2ghz, 'modes': mode_2Ghz}]


    def is_security_mode_supported(self, security_mode):
        return security_mode in (self.security_type_disabled,
                                 self.security_type_wpapsk,
                                 self.security_type_wep)


    def navigate_to_page(self, page_number):
        if page_number != 1:
            raise RuntimeError('Invalid page number passed.  Number of pages '
                               '%d, page value sent was %d' %
                               (self.get_number_of_pages(), page_number))
        page_url = urlparse.urljoin(self.admin_interface_url,
                                    'WLG_wireless_dual_band.htm')
        self.get_url(page_url, page_title='NETGEAR Router')
        self.wait_for_object_by_xpath('//input[@name="ssid" and @type="text"]')


    def save_page(self, page_number):
        self.click_button_by_xpath('//button[@name="Apply"]',
                                   alert_handler=self._alert_handler)


    def set_mode(self, mode):
        self.add_item_to_command_list(self._set_mode, (mode, ), 1, 900)


    def _set_mode(self, mode):
        xpath = '//select[@name="opmode"]'
        if self.current_band == self.band_5ghz:
            xpath = '//select[@name="opmode_an"]'
        self.select_item_from_popup_by_xpath(mode, xpath)


    def set_radio(self, enabled=True):
        #  We cannot turn off the radio in Netgear
        return None


    def set_ssid(self, ssid):
        self.add_item_to_command_list(self._set_ssid, (ssid,), 1, 900)


    def _set_ssid(self, ssid):
        xpath = '//input[@name="ssid"]'
        if self.current_band == self.band_5ghz:
           xpath = '//input[@name="ssid_an"]'
        self.set_content_of_text_field_by_xpath(ssid, xpath)


    def set_channel(self, channel):
        self.add_item_to_command_list(self._set_channel, (channel,), 1, 900)


    def _set_channel(self, channel):
        position = self._get_channel_popup_position(channel)
        channel_choices = ['Auto', '01', '02', '03', '04', '05', '06', '07',
                           '08', '09', '10', '11']
        xpath = '//select[@name="w_channel"]'
        if self.current_band == self.band_5ghz:
            xpath = '//select[@name="w_channel_an"]'
            channel_choices = ['Auto', '36', '40', '44', '48', '149', '153',
                               '157', '161', '165']
        self.select_item_from_popup_by_xpath(channel_choices[position],
                                             xpath,
                                             alert_handler=self._alert_handler)


    def set_band(self, band):
        if band == self.band_5ghz:
            self.current_band = self.band_5ghz
        elif band == self.band_2ghz:
            self.current_band = self.band_2ghz
        else:
            raise RuntimeError('Invalid band sent %s' % band)


    def set_security_disabled(self):
        self.add_item_to_command_list(self._set_security_disabled, (), 1, 900)


    def _set_security_disabled(self):
        xpath = ('//input[@name="security_type" and @value="Disable"]')
        if self.current_band == self.band_5ghz:
            xpath = ('//input[@name="security_type_an" and @value="Disable"]')
        self.click_button_by_xpath(xpath, alert_handler=self._alert_handler)


    def set_security_wep(self, key_value, authentication):
        # The button name seems to differ in various Netgear routers
        self.add_item_to_command_list(self._set_security_wep,
                                      (key_value, authentication), 1, 900)


    def _set_security_wep(self, key_value, authentication):
        xpath = '//input[@name="security_type" and @value="WEP" and\
                 @type="radio"]'
        text_field = '//input[@name="passphraseStr"]'
        button = '//button[@name="keygen"]'
        if self.current_band == self.band_5ghz:
            xpath = '//input[@name="security_type_an" and @value="WEP" and\
                     @type="radio"]'
            text_field = '//input[@name="passphraseStr_an"]'
            button = '//button[@name="Generate_an"]'
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


    def set_security_wpapsk(self, shared_key):
        self.add_item_to_command_list(self._set_security_wpapsk,
                                      (shared_key,), 1, 900)


    def _set_security_wpapsk(self, shared_key):
        xpath = ('//input[@name="security_type" and @value="WPA-PSK"]')
        text = '//input[@name="passphrase"]'
        if self.current_band == self.band_5ghz:
            xpath = ('//input[@name="security_type_an" and @value="WPA-PSK"]')
            text = '//input[@name="passphrase_an"]'
        try:
            self.click_button_by_xpath(xpath,
                                       alert_handler=self._alert_handler)
        except Exception, e:
            raise RuntimeError('For WPA-PSK the mode should be 54Mbps. %s' % e)
        self.set_content_of_text_field_by_xpath(shared_key, text,
                                                abort_check=True)


    def set_visibility(self, visible=True):
        self.add_item_to_command_list(self._set_visibility, (visible,), 1, 900)


    def _set_visibility(self, visible=True):
        xpath = '//input[@name="ssid_bc" and @type="checkbox"]'
        if self.current_band == self.band_5ghz:
            xpath = '//input[@name="ssid_bc_an" and @type="checkbox"]'
        self.set_check_box_selected_by_xpath(xpath, selected=visible,
                                             wait_for_xpath=None,
                                             alert_handler=self._alert_handler)
