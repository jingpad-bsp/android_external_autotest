# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import urlparse
import time

import ap_configurator

from selenium.common.exceptions import WebDriverException


class WesternDigitalN600APConfigurator(ap_configurator.APConfigurator):
    """Base class for objects to configure Western Digital N600 access point
       using webdriver."""


    def __init__(self, ap_config=None):
        super(WesternDigitalN600APConfigurator, self).__init__(ap_config=
                                                               ap_config)
        self.current_band = self.band_2ghz


    def _sec_alert(self, alert):
        text = alert.text
        if 'Your wireless security mode is not compatible with' in text:
            alert.accept()
        elif 'WARNING: Your Wireless-N devices will only operate' in text:
            alert.accept()
        elif 'Your new setting will disable Wi-Fi Protected Setup.' in text:
            alert.accept()
        elif 'To use WEP security, WPS must be disabled. Proceed ?' in text:
             alert.accept()
        elif 'Warning ! Selecting None in Security Mode will make \
             your 5 GHz wifi connection vulnerable. Continue ?' in text:
             alert.accept()
        else:
           raise RuntimeError('Invalid handler')


    def get_number_of_pages(self):
        return 1


    def get_supported_modes(self):
        return [{'band': self.band_2ghz,
                 'modes': [self.mode_b, self.mode_g, self.mode_b | self.mode_g,
                           self.mode_n, self.mode_g | self.mode_n,
                           self.mode_b | self.mode_g | self.mode_n]},
                {'band': self.band_5ghz,
                 'modes': [self.mode_a, self.mode_n,
                           self.mode_a | self.mode_n]}]


    def get_supported_bands(self):
        return [{'band': self.band_2ghz,
                 'channels': ['auto', 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]},
                {'band': self.band_5ghz,
                 'channels': ['auto', 36, 40, 44, 48, 149, 153, 157, 161, 165]}]


    def is_security_mode_supported(self, security_mode):
        return security_mode in (self.security_type_disabled,
                                 self.security_type_wpapsk,
                                 self.security_type_wpa2psk,
                                 self.security_type_wep)


    def navigate_to_page(self, page_number):
       self.get_url(self.admin_interface_url, page_title='WESTERN DIGITAL')
       logout = '//input[@type="button" and @value="Log Out"]'
       # We are using try here to catch an exception in case landing page
       # is not loaded and directed to dashboard instead.
       try:
           self.wait_for_object_by_id('loginusr')
           self.set_content_of_text_field_by_id('admin', 'loginusr',
                                                 abort_check=True)
           self.set_content_of_text_field_by_id('password', 'loginpwd',
                                                abort_check=True)
           self.click_button_by_xpath('//input[@value="Submit"]')
           # Give some time to go to Wireless settings page.
           self.wait_for_object_by_xpath(logout, wait_time=5)
       except:
           if not self.wait_for_object_by_xpath(logout):
              raise RuntimeError('We did not load the landing page')
       page_url = urlparse.urljoin(self.admin_interface_url, 'wlan.php')
       self.get_url(page_url, page_title='WESTERN DIGITAL')


    def save_page(self, page_number):
        self.wait_for_object_by_id('onsumit')
        self.click_button_by_id('onsumit', alert_handler=self._sec_alert)
        warning = '//h1[text()="Warning"]'
        settings_changed = True
        try:
            self.wait_for_object_by_xpath(warning)
            self.driver.find_elements_by_id('onsumit')[1].click()
            self.wait_for_object_by_xpath('//input[@value="Ok"]', wait_time=5)
        except WebDriverException, e:
            logging.info('There is a webdriver exception: "%s".' % str(e))
            settings_changed = False
        if not settings_changed:
            try:
                # if settings are not changed, hit 'continue' button.
                self.driver.find_element_by_id('nochg')
                self.click_button_by_id('nochg')
            except WebDriverException, e:
                logging.info('There is a webdriver exception: "%s".' % str(e))


    def set_mode(self, mode, band=None):
        self.add_item_to_command_list(self._set_mode, (mode,), 1, 900)


    def _set_mode(self, mode, band=None):
        mode_mapping = {self.mode_b | self.mode_g:'Mixed 802.11 b+g',
                        self.mode_g:'802.11g only',
                        self.mode_b:'802.11b only',
                        self.mode_n:'802.11n only',
                        self.mode_a:'802.11a only',
                        self.mode_g | self.mode_n:'Mixed 802.11 g+n',
                        self.mode_b | self.mode_g | self.mode_n:
                        'Mixed 802.11 b+g+n',
                        self.mode_a | self.mode_n: 'Mixed 802.11 a+n'}
        mode_id = 'wlan_mode'
        if self.current_band == self.band_5ghz:
            mode_id = 'wlan_mode_Aband'
        mode_name = ''
        if mode in mode_mapping.keys():
            mode_name = mode_mapping[mode]
            if (mode & self.mode_a) and (self.current_band != self.band_5ghz):
                # a mode only in 5Ghz
                logging.info('Mode \'a\' is not supported for 2.4Ghz band.')
                return
            elif ((mode & (self.mode_b | self.mode_g) ==
                  (self.mode_b | self.mode_g)) or
                 (mode & self.mode_b == self.mode_b) or
                 (mode & self.mode_g == self.mode_g)) and \
                 (self.current_band != self.band_2ghz):
                # b/g, b, g mode only in 2.4Ghz
                logging.info('Mode \'%s\' is not available for 5Ghz band.'
                             % mode_name)
                return
        else:
            raise RuntimeError('The mode selected \'%d\' is not supported by '
                               ' \'%s\'.', hex(mode), self.get_router_name())
        self.select_item_from_popup_by_id(mode_name, mode_id,
                                          alert_handler=self._sec_alert)


    def set_ssid(self, ssid):
        self.add_item_to_command_list(self._set_ssid, (ssid,), 1, 900)


    def _set_ssid(self, ssid):
        ssid_id = 'ssid'
        if self.current_band == self.band_5ghz:
            ssid_id = 'ssid_Aband'
        self.wait_for_object_by_id(ssid_id)
        self.set_content_of_text_field_by_id(ssid, ssid_id, abort_check=False)


    def set_channel(self, channel):
        self.add_item_to_command_list(self._set_channel, (channel,), 1, 900)


    def _set_channel(self, channel):
        position = self._get_channel_popup_position(channel)
        channel_id = 'channel'
        channel_choices = ['Auto', '2.412 GHz - CH 1', '2.417 GHz - CH 2',
                           '2.422 GHz - CH 3', '2.427 GHz - CH 4',
                           '2.432 GHz - CH 5', '2.437 GHz - CH 6',
                           '2.442 GHz - CH 7', '2.447 GHz - CH 8',
                           '2.452 GHz - CH 9', '2.457 GHz - CH 10',
                           '2.462 GHz - CH 11']
        if self.current_band == self.band_5ghz:
            channel_id = 'channel_Aband'
            channel_choices = ['Auto', '5.180 GHz - CH 36', '5.200 GHz - CH 40',
                               '5.220 GHz - CH 44', '5.240 GHz - CH 48',
                               '5.745 GHz - CH 149', '5.765 GHz - CH 153',
                               '5.785 GHz - CH 157', '5.805 GHz - CH 161',
                               '5.825 GHz - CH 165']
        self.select_item_from_popup_by_id(channel_choices[position], channel_id)


    def set_channel_width(self, channel_wid):
        self.add_item_to_command_list(self._set_channel_width, (channel_wid,),
                                      1, 900)


    def _set_channel_width(self, channel_wid):
        channel_width_choice = ['20 MHz', '20/40 MHz(Auto)']
        width_id = 'bw'
        if self.current_band == self.band_5ghz:
            width_id = 'bw_Aband'
        self.select_item_from_popup_by_id(channel_width_choice[channel_wid],
                                          width_id)


    def set_radio(self, enabled=True):
        logging.info('set_radio is not supported in Western Digital N600 AP.')
        return None


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
        self.security_disabled = 'None'
        dis_id = 'security_type'
        if self.current_band == self.band_5ghz:
            dis_id = 'security_type_Aband'
        self.select_item_from_popup_by_id(self.security_disabled, dis_id,
                                          alert_handler=self._sec_alert)


    def set_security_wep(self, key_value, authentication):
        self.add_item_to_command_list(self._set_security_wep,
                                      (key_value, authentication), 1, 900)


    def _set_security_wep(self, key_value, authentication):
        # WEP is not supported for Wireless-N only and Mixed (g+n, b+g+n) mode.
        # WEP does not show up in the list, no alert is thrown.
        self.security_wep = 'WEP'
        sec_id = 'security_type'
        text = '//input[@name="wepkey_64"]'
        if self.current_band == self.band_5ghz:
            sec_id = 'security_type_Aband'
            text = '//input[@name="wepkey_64_Aband"]'
        if not self.item_in_popup_by_id_exist(self.security_wep, sec_id):
            raise RuntimeError('The popup %s did not contain the item %s. '
                               'Is the mode N?' % (sec_id, self.security_wep))
        self.wait_for_object_by_id(sec_id, wait_time=5)
        wep = self.item_in_popup_by_id_exist(self.security_wep, sec_id)
        if wep:
            self.select_item_from_popup_by_id(self.security_wep, sec_id,
                                              wait_for_xpath=text,
                                              alert_handler=None)
            self.set_content_of_text_field_by_xpath(key_value, text,
                                                    abort_check=True)


    def set_security_wpapsk(self, shared_key, update_interval=None):
        # WEP and WPA-Personal are not supported for Wireless-N only mode,
        # so use WPA2-Personal to avoid conflicts.
        self.add_item_to_command_list(self._set_security_wpa2psk,
                                      (shared_key,), 1, 900)


    def _set_security_wpa2psk(self, shared_key):
        self.security_wpa2psk = 'WPA2 - Personal'
        logging.info('update_interval is not supported.')
        sec_id = 'security_type'
        text = '//input[@name="wpapsk" and @type="text"]'
        if self.current_band == self.band_5ghz:
            sec_id = 'security_type_Aband'
            text = '//input[@name="wpapsk_Aband" and @type="text"]'
        self.wait_for_object_by_id(sec_id, wait_time=5)
        wpa = self.item_in_popup_by_id_exist(self.security_wpa2psk, sec_id)
        if wpa:
            self.select_item_from_popup_by_id(self.security_wpa2psk, sec_id,
                                              alert_handler=None)
            self.set_content_of_text_field_by_xpath(shared_key, text,
                                                    abort_check=False)


    def set_visibility(self, visible=True):
        self.add_item_to_command_list(self._set_visibility, (visible,), 1, 900)


    def _set_visibility(self, visible=True):
        logging.info("SSID broadcast is not supported for Western Digital N600")
        return None
