# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Base class for objects to configure Linksys single band access points
   using webdriver."""

import logging
import urlparse

import ap_configurator

from selenium.common.exceptions import WebDriverException


class LinksyseSingleBandAPConfigurator(ap_configurator.APConfigurator):
    """Base class for objects to configure Linksys single band access points
       using webdriver."""

    def _sec_alert(self, alert):
        text = alert.text
        if 'Your wireless security mode is not compatible with' in text:
            alert.accept()
        elif 'WARNING: Your Wireless-N devices will only operate' in text:
            alert.accept()
        elif 'Wireless security is currently disabled.' in text:
            alert.accept()
            self.click_button_by_id('divBT1', alert_handler=self._sec_alert)
            self.click_button_by_xpath('//input[@value="Continue"]')
        elif 'Your new setting will disable Wi-Fi Protected Setup.' in text:
            alert.accept()
        elif 'Illegal characters [ acceptable characters: 0 to 9 ]' in text:
            alert.accept()
            raise RuntimeError('Invalid characters used for key renewal. '
                               'Error: %s' % text)
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
                 'channels': ['Auto', 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]}]


    def is_security_mode_supported(self, security_mode):
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


    def save_page(self, page_number):
        self.click_button_by_id('divBT1', alert_handler=self._sec_alert)
        self.click_button_by_xpath('//input[@value="Continue"]')


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
        # If security is off leaving focus from the field will throw
        # a alert dialog.
        ssid_field = self.driver.find_element_by_xpath(xpath)
        try:
            ssid_field.send_keys('\t')
            return
        except WebDriverException, e:
            message = str(e)
            if message.find('An open modal dialog blocked the operation') == -1:
                return
        self._sec_alert(self.driver.switch_to_alert())


    def set_channel(self, channel):
        self.add_item_to_command_list(self._set_channel, (channel,), 1, 900)


    def _set_channel(self, channel):
        position = self._get_channel_popup_position(channel)
        xpath = '//select[@name="_wl0_channel"]'
        channels = ['Auto',
                    '1 - 2.412GHZ', '2 - 2.417GHZ', '3 - 2.422GHZ',
                    '4 - 2.427GHZ', '5 - 2.432GHZ', '6 - 2.437GHZ',
                    '7 - 2.442GHZ', '8 - 2.447GHZ', '9 - 2.452GHZ',
                    '10 - 2.457GHZ', '11 - 2.462GHZ']
        self.select_item_from_popup_by_xpath(channels[position], xpath)


    def set_channel_width(self, channel_wid):
        """
        Adjusts the channel channel width.

        @param channel_width: the channel width
        """
        self.add_item_to_command_list(self._set_channel_width,(channel_wid,),
                                      1, 900)


    def _set_channel_width(self, channel_wid):
        channel_width_choice = ['Auto (20 MHz or 40 MHz)', '20 MHz Only']
        xpath = '//select[@name="_wl0_nbw"]'
        self.select_item_from_popup_by_xpath(channel_width_choice[channel_wid],
                                             xpath)


    def set_radio(self, enabled=True):
        logging.debug('set_radio is not supported in Linksys single band AP.')
        return None


    def set_band(self, enabled=True):
        logging.debug('set_band is not supported in Linksys single band AP.')
        return None


    def set_security_disabled(self):
        self.add_item_to_command_list(self._set_security_disabled, (), 2, 1000)


    def _set_security_disabled(self):
        xpath = '//select[@name="wl0_security_mode"]'
        self.select_item_from_popup_by_xpath('Disabled', xpath,
                                             alert_handler=self._sec_alert)


    def set_security_wep(self, key_value, authentication):
        self.add_item_to_command_list(self._set_security_wep,
                                      (key_value, authentication), 2, 1000)


    def _set_security_wep(self, key_value, authentication):
        # WEP and WPA-Personal are not supported for Wireless-N only mode
        # and Mixed mode.
        # WEP and WPA-Personal do not show up in the list, no alert is thrown.
        popup = '//select[@name="wl0_security_mode"]'
        if not self.item_in_popup_by_xpath_exist('WEP', popup):
            raise RuntimeError('The popup %s did not contain the item %s. '
                               'Is the mode N?' % (popup, self.security_wep))
        self.select_item_from_popup_by_xpath('WEP', popup,
                                             alert_handler=self._sec_alert)
        text = '//input[@name="wl0_passphrase"]'
        self.set_content_of_text_field_by_xpath(key_value, text,
                                                abort_check=True)
        xpath = '//input[@value="Generate"]'
        self.click_button_by_xpath(xpath, alert_handler=self._sec_alert)


    def set_security_wpapsk(self, shared_key, update_interval=None):
        # WEP and WPA-Personal are not supported for Wireless-N only mode,
        # so use WPA2-Personal when in mode_n.
        self.add_item_to_command_list(self._set_security_psk, (shared_key,
                                      update_interval, 'WPA Personal'), 2, 900)


    def set_security_wpa2psk(self, shared_key, update_interval=None):
        """Enabled WPA2 using a private security key for the wireless network.

        @param shared_key: shared encryption key to use
        @param update_interval: number of seconds to wait before updating
        """
        # WEP and WPA-Personal are not supported for Wireless-N only mode,
        # so use WPA2-Personal when in mode_n.
        self.add_item_to_command_list(self._set_security_psk, (shared_key,
                                      update_interval, 'WPA2 Personal'), 2, 900)


    def _set_security_psk(self, shared_key, upadate_interval=None,
                          rsn_mode='WPA Personal'):
        """Common method to set wpapsk and wpa2psk modes."""
        popup = '//select[@name="wl0_security_mode"]'
        self.select_item_from_popup_by_xpath(rsn_mode, popup,
                                             alert_handler=self._sec_alert)
        text = '//input[@name="wl0_wpa_psk"]'
        self.set_content_of_text_field_by_xpath(shared_key, text,
                                                abort_check=False)


    def is_update_interval_supported(self):
        """
        Returns True if setting the PSK refresh interval is supported.

        @return True is supported; False otherwise
        """
        return False


    def set_visibility(self, visible=True):
        self.add_item_to_command_list(self._set_visibility, (visible,), 1, 900)


    def _set_visibility(self, visible=True):
        int_value = 0 if visible else 1
        xpath = ('//input[@value="%d" and @name="closed_24g"]' % int_value)
        self.click_button_by_xpath(xpath, alert_handler=self._sec_alert)
