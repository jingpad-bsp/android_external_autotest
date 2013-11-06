# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import urlparse
import time

import dynamic_ap_configurator
import ap_spec

from selenium.common.exceptions import WebDriverException


class WesternDigitalN600APConfigurator(
        dynamic_ap_configurator.DynamicAPConfigurator):
    """Base class for objects to configure Western Digital N600 access point
       using webdriver."""


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
        elif 'Warning ! Selecting None in Security Mode will make' in text:
             alert.accept()
        else:
           raise RuntimeError('Invalid handler')


    def get_number_of_pages(self):
        return 1


    def is_update_interval_supported(self):
        """
        Returns True if setting the PSK refresh interval is supported.

        @return True is supported; False otherwise
        """
        return False


    def get_supported_modes(self):
        return [{'band': ap_spec.BAND_2GHZ,
                 'modes': [ap_spec.MODE_B, ap_spec.MODE_G, ap_spec.MODE_N,
                           ap_spec.MODE_B | ap_spec.MODE_G,
                           ap_spec.MODE_G | ap_spec.MODE_N,
                           ap_spec.MODE_B | ap_spec.MODE_G | ap_spec.MODE_N]},
                {'band': ap_spec.BAND_5GHZ,
                 'modes': [ap_spec.MODE_A, ap_spec.MODE_N,
                           ap_spec.MODE_A | ap_spec.MODE_N]}]


    def get_supported_bands(self):
        return [{'band': ap_spec.BAND_2GHZ,
                 'channels': ['Auto', 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]},
                {'band': ap_spec.BAND_5GHZ,
                 'channels': ['Auto', 36, 40, 44, 48, 149, 153, 157, 161, 165]}]


    def is_security_mode_supported(self, security_mode):
        return security_mode in (ap_spec.SECURITY_TYPE_DISABLED,
                                 ap_spec.SECURITY_TYPE_WPAPSK,
                                 ap_spec.SECURITY_TYPE_WPA2PSK,
                                 ap_spec.SECURITY_TYPE_WEP)


    def navigate_to_page(self, page_number):
        page_url = urlparse.urljoin(self.admin_interface_url, 'wlan.php')
        self.get_url(page_url, page_title='WESTERN DIGITAL')
        xpath_found = self.wait_for_objects_by_id(['loginusr', 'ssid'])
        switch = '//input[@id="en_wifi"]/../span[@class="checkbox"]'
        if 'loginusr' in xpath_found:
            self._login_to_router()
        elif 'ssid' not in xpath_found:
            raise RuntimeError('The page %s did not load or Radio is switched'
                               'off' % page_url)
        else:
            if self.current_band == ap_spec.BAND_5GHZ:
                switch = '//input[@id="en_wifi_Aband"]/../ \
                          span[@class="checkbox"]'
            for timer in range(30):   # Waiting for the page to reload
                on_off = self.driver.find_element_by_xpath(switch)
                try:
                    if ('checkbox.png' in
                        on_off.value_of_css_property('background-image')):
                        return None
                except:
                    pass
                time.sleep(1)


    def _login_to_router(self):
        self.wait_for_object_by_id('loginusr')
        self.set_content_of_text_field_by_id('admin', 'loginusr',
                                             abort_check=True)
        self.set_content_of_text_field_by_id('password', 'loginpwd',
                                             abort_check=True)
        self.click_button_by_xpath('//input[@value="Submit"]')
        # Give some time to go to Wireless settings page.
        self.wait_for_object_by_id('ssid')


    def save_page(self, page_number):
        self.wait_for_object_by_id('onsumit')
        self.click_button_by_id('onsumit', alert_handler=self._sec_alert)
        warning = '//h1[text()="Warning"]'
        settings_changed = True
        try:
            self.wait_for_object_by_xpath(warning)
            xpath = '//input[@id="onsumit"]'
            button = self.driver.find_elements_by_xpath(xpath)[1]
            button.click()
            self._handle_alert(xpath, self._sec_alert)
            self.wait_for_object_by_xpath('//input[@value="Ok"]', wait_time=5)
        except WebDriverException, e:
            logging.debug('There is a webdriver exception: "%s".', str(e))
            settings_changed = False
        if not settings_changed:
            try:
                # if settings are not changed, hit 'continue' button.
                self.driver.find_element_by_id('nochg')
                self.click_button_by_id('nochg')
            except WebDriverException, e:
                logging.debug('There is a webdriver exception: "%s".', str(e))


    def set_mode(self, mode, band=None):
        self.add_item_to_command_list(self._set_mode, (mode,), 1, 900)


    def _set_mode(self, mode, band=None):
        mode_mapping = {ap_spec.MODE_B | ap_spec.MODE_G:'Mixed 802.11 b+g',
                        ap_spec.MODE_G:'802.11g only',
                        ap_spec.MODE_B:'802.11b only',
                        ap_spec.MODE_N:'802.11n only',
                        ap_spec.MODE_A:'802.11a only',
                        ap_spec.MODE_G | ap_spec.MODE_N:'Mixed 802.11 g+n',
                        ap_spec.MODE_B | ap_spec.MODE_G | ap_spec.MODE_N:
                        'Mixed 802.11 b+g+n',
                        ap_spec.MODE_A | ap_spec.MODE_N: 'Mixed 802.11 a+n'}
        mode_id = 'wlan_mode'
        if self.current_band == ap_spec.BAND_5GHZ:
            mode_id = 'wlan_mode_Aband'
        mode_name = ''
        if mode in mode_mapping.keys():
            mode_name = mode_mapping[mode]
            if ((mode & ap_spec.MODE_A) and
                (self.current_band != ap_spec.BAND_5GHZ)):
                # a mode only in 5Ghz
                logging.debug('Mode \'a\' is not supported for 2.4Ghz band.')
                return
            elif ((mode & (ap_spec.MODE_B | ap_spec.MODE_G) ==
                  (ap_spec.MODE_B | ap_spec.MODE_G)) or
                 (mode & ap_spec.MODE_B == ap_spec.MODE_B) or
                 (mode & ap_spec.MODE_G == ap_spec.MODE_G)) and \
                 (self.current_band != ap_spec.BAND_2GHZ):
                # b/g, b, g mode only in 2.4Ghz
                logging.debug('Mode \'%s\' is not available for 5Ghz band.',
                              mode_name)
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
        if self.current_band == ap_spec.BAND_5GHZ:
            ssid_id = 'ssid_Aband'
        self.wait_for_object_by_id(ssid_id)
        self.set_content_of_text_field_by_id(ssid, ssid_id, abort_check=False)
        self._ssid = ssid


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
        if self.current_band == ap_spec.BAND_5GHZ:
            channel_id = 'channel_Aband'
            channel_choices = ['Auto', '5.180 GHz - CH 36', '5.200 GHz - CH 40',
                               '5.220 GHz - CH 44', '5.240 GHz - CH 48',
                               '5.745 GHz - CH 149', '5.765 GHz - CH 153',
                               '5.785 GHz - CH 157', '5.805 GHz - CH 161',
                               '5.825 GHz - CH 165']
        self.wait_for_object_by_id(channel_id)
        self.select_item_from_popup_by_id(channel_choices[position], channel_id)


    def set_channel_width(self, channel_wid):
        self.add_item_to_command_list(self._set_channel_width, (channel_wid,),
                                      1, 900)


    def _set_channel_width(self, channel_wid):
        channel_width_choice = ['20 MHz', '20/40 MHz(Auto)']
        width_id = 'bw'
        if self.current_band == ap_spec.BAND_5GHZ:
            width_id = 'bw_Aband'
        self.select_item_from_popup_by_id(channel_width_choice[channel_wid],
                                          width_id)


    def set_radio(self, enabled=True):
        logging.debug('set_radio is not supported in Western Digital N600 AP.')
        return None


    def set_band(self, band):
        if band == ap_spec.BAND_5GHZ:
            self.current_band = ap_spec.BAND_5GHZ
        elif band == ap_spec.BAND_2GHZ:
            self.current_band = ap_spec.BAND_2GHZ
        else:
            raise RuntimeError('Invalid band sent %s' % band)


    def _set_security(self, security_type, wait_path=None):
        sec_id = 'security_type'
        if self.current_band == ap_spec.BAND_5GHZ:
            sec_id = 'security_type_Aband'
            text = '//input[@name="wpapsk_Aband" and @type="text"]'
        self.wait_for_object_by_id(sec_id, wait_time=5)
        if self.item_in_popup_by_id_exist(security_type, sec_id):
            self.select_item_from_popup_by_id(security_type, sec_id,
                                              wait_for_xpath=wait_path,
                                              alert_handler=self._sec_alert)
        elif security_type == 'WEP':
            raise RuntimeError('Could not set up WEP security. '
                               'Please check the mode. Mode-N does not '
                               'support WEP.')
        else:
            raise RuntimeError('The dropdown %s does not have item %s' %
                               (sec_id, security_type))


    def set_security_disabled(self):
        self.add_item_to_command_list(self._set_security_disabled, (), 1, 1000)


    def _set_security_disabled(self):
        self._set_security('None')


    def set_security_wep(self, key_value, authentication):
        self.add_item_to_command_list(self._set_security_wep,
                                      (key_value, authentication), 1, 1000)


    def _set_security_wep(self, key_value, authentication):
        # WEP is not supported for Wireless-N only and Mixed (g+n, b+g+n) mode.
        # WEP does not show up in the list, no alert is thrown.
        text = '//input[@name="wepkey_64"]'
        if self.current_band == ap_spec.BAND_5GHZ:
            text = '//input[@name="wepkey_64_Aband"]'
        self._set_security('WEP', text)
        self.set_content_of_text_field_by_xpath(key_value, text,
                                                abort_check=True)


    def set_security_wpapsk(self, security, shared_key, update_interval=None):
        # WEP and WPA-Personal are not supported for Wireless-N only mode,
        self.add_item_to_command_list(self._set_security_wpapsk,
                                      (security, shared_key,), 1, 1000)


    def _set_security_wpapsk(self, security, shared_key):
        text = 'wpapsk'
        if self.current_band == ap_spec.BAND_5GHZ:
            text = 'wpapsk_Aband'
        if security == ap_spec.SECURITY_TYPE_WPAPSK:
            self._set_security('WPA - Personal', '//input[@id="%s"]' % text)
        else:
            self._set_security('WPA2 - Personal', '//input[@id="%s"]' % text)
        self.set_content_of_text_field_by_id(shared_key, text,
                                             abort_check=False)


    def set_visibility(self, visible=True):
        self.add_item_to_command_list(self._set_visibility, (visible,), 1, 900)


    def _set_visibility(self, visible=True):
        status = True
        visibility = '//input[@id="ssid_visible"]/../span[@class="checkbox"]'
        ssid_switch = self.driver.find_element_by_xpath(visibility)
        if ('checkbox_off.png' in
            ssid_switch.value_of_css_property('background-image')):
            status = False
        if (not visible and status) or (visible and not status):
            self.click_button_by_xpath(visibility)
