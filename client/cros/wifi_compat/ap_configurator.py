# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import binascii
import copy
import logging
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__),
    '../../deps/chrome_test/test_src/third_party/webdriver/pylib'))

try:
  from selenium import webdriver
except ImportError:
  raise ImportError('Could not locate the webdriver package.  Did you build? '
                    'Are you using a prebuilt autotest package?')

from selenium.common.exceptions import TimeoutException as \
    SeleniumTimeoutException
from selenium.webdriver.support.ui import WebDriverWait


class APConfigurator(object):
    """Base class for objects to configure access points using webdriver."""

    def __init__(self, router_dict):
        # Possible bands
        self.band_2ghz = '2.4GHz'
        self.band_5ghz = '5GHz'

        # Possible modes
        self.mode_a = 0x0001
        self.mode_b = 0x0010
        self.mode_g = 0x0100
        self.mode_n = 0x1000

        # Possible security settings
        self.security_disabled = 'Disabled'
        self.security_wep = 'WEP'
        self.security_wpawpsk = 'WPA-Personal'
        self.security_wpa2wpsk = 'WPA2-Personal'
        self.security_wpa8021x = 'WPA-Enterprise'
        self.security_wpa28021x = 'WPA2-Enterprise'

        self.wep_authentication_open = 'Open'
        self.wep_authentication_shared = 'Shared Key'

        self.admin_interface_url = router_dict['admin_url']
        self.class_name = router_dict['class_name']
        self.short_name = router_dict['short_name']
        self.serial_number = router_dict['serial_number']
        self.mac_address = router_dict['mac_address']

        self._command_list = []

    def __del__(self):
        try:
            self.driver.close()
        except:
            pass

    def wait_for_object_by_id(self, element_id):
        """Waits for an element to become available; returns a reference to it.

        Args:
          element_id: the id of the element to wait for

        Returns:
          Reference to the element if found.
        """
        xpath = 'id("%s")' % element_id
        return self.wait_for_object_by_xpath(xpath)

    def wait_for_object_by_xpath(self, xpath):
        """Waits for an element to become available; returns a reference to it.

        Args:
          xpath: the xpath of the element to wait for

        Returns:
          Reference to the element if found.
        """
        try:
            self.wait.until(lambda _: self.driver.find_element_by_xpath(xpath))
        except SeleniumTimeoutException, e:
            raise SeleniumTimeoutException('Unable to find the object by xpath:'
                                           '%s\n WebDriver exception: %s',
                                           xpath, str(e))
        return self.driver.find_element_by_xpath(xpath)

    def select_item_from_popup_by_id(self, item, element_id,
                                     wait_for_xpath=None):
        """Selects an item from a popup, by passing the element ID.

        Args:
          item: the item to select from the popup
          element_id: the html ID of the item
          wait_for_xpath: an item to wait for before returning
        """
        xpath = 'id("%s")' % element_id
        self.select_item_from_popup_by_xpath(item, xpath, wait_for_xpath)

    def select_item_from_popup_by_xpath(self, item, xpath, wait_for_xpath=None):
        """Selects an item from a popup, by passing the xpath of the popup.

        Args:
          item: the item to select from the popup
          xpath: the xpath of the popup
          wait_for_xpath: an item to wait for before returning
        """
        popup = self.driver.find_element_by_xpath(xpath)
        try:
            self.wait.until(lambda _:
                            len(popup.find_elements_by_tag_name('option')))
        except SeleniumTimeoutException, e:
            raise SeleniumTimeoutException('The popup at xpath %s has no items.'
                                           '\n WebDriver exception: %s', xpath,
                                           str(e))
        for option in popup.find_elements_by_tag_name('option'):
            if option.text == item:
                option.click()
                break
        if wait_for_xpath: self.wait_for_object_by_xpath(wait_for_xpath)

    def set_content_of_text_field_by_id(self, content, text_field_id,
                                        wait_for_xpath=None):
        """Sets the content of a textfield, by passing the element ID.

        Args:
          content: the content to apply to the textfield
          text_field_id: the html ID of the textfield
          wait_for_xpath: an item to wait for before returning
        """
        xpath = 'id("%s")' % text_field_id
        self.set_content_of_text_field_by_xpath(content, xpath, wait_for_xpath)

    def set_content_of_text_field_by_xpath(self, content, xpath,
                                           wait_for_xpath=None):
        """Sets the content of a textfield, by passing the xpath.

        Args:
          content: the content to apply to the textfield
          xpath: the xpath of the textfield
          wait_for_xpath: an item to wait for before returning
        """
        # When we can get the value we know the text field is ready.
        text_field = self.driver.find_element_by_xpath(xpath)
        try:
            self.wait.until(lambda _: text_field.get_attribute('value'))
        except SeleniumTimeoutException, e:
            raise SeleniumTimeoutException('Unable to obtain the value of the '
                                           'text field %s.\nWebDriver '
                                           'exception: %s',
                                           wait_for_xpath, str(e))
        text_field = self.driver.find_element_by_xpath(xpath)
        text_field.clear()
        text_field.send_keys(content)
        if wait_for_xpath: self.wait_for_object_by_xpath(wait_for_xpath)

    def set_check_box_selected_by_id(self, check_box_id, selected=True,
                                     wait_for_xpath=None):
        """Sets the state of a checkbox, by passing the ID.

        Args:
          check_box_id: the html id of the checkbox
          selected: True to enable the checkbox; False otherwise
          wait_for_xpath: an item to wait for before returning
        """
        xpath = 'id("%s")' % check_box_id
        self.set_check_box_selected_by_xpath(xpath, selected, wait_for_xpath)

    def set_check_box_selected_by_xpath(self, xpath, selected=True,
                                        wait_for_xpath=None):
        """Sets the state of a checkbox, by passing the xpath.

        Args:
          xpath: the xpath of the checkbox
          selected: True to enable the checkbox; False otherwise
          wait_for_xpath: an item to wait for before returning
        """
        check_box = self.driver.find_element_by_xpath(xpath)
        value = check_box.get_attribute('value')
        if (value == '1' and not selected) or (value == '0' and selected):
            check_box.click()
        if wait_for_xpath:
            self.wait_for_object_by_xpath(wait_for_xpath)

    def add_item_to_command_list(self, method, args, page, priority):
        """Adds commands to be executed against the AP web UI.

        Args:
          method: the method to run
          args: the arguments for the method you want executed
          page: the page on the web ui where the method should be run against
          priority: the priority of the method
        """
        self._command_list.append({'method': method,
                                   'args': copy.copy(args),
                                   'page': page,
                                   'priority': priority})

    def get_router_name(self):
        """Returns a string to describe the router."""
        return ('Router name: %s, Controller class: %s, Serial: %s, MAC '
                'Address: %s' % (self.short_name, self.class_name,
                                 self.serial_number, self.mac_address))

    def get_router_short_name(self):
        """Returns a short string to describe the router."""
        return self.short_name

    def get_number_of_pages(self):
        """Returns the number of web pages used to configure the router.

        Note: This is used internally by apply_settings, and this method must be
              implemented by the derived class.

        Note: The derived class must implement this method.

        """
        raise NotImplementedError

    def get_supported_bands(self):
        """Returns a list of dictionaries describing the supported bands.

        Example: returned is a dictionary of band and a list of channels. The
                 band object returned must be one of those defined in the
                 __init___ of this class.

        supported_bands = [{'band' : self.band_2GHz,
                            'channels' : [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]},
                           {'band' : self.band_5ghz,
                            'channels' : [26, 40, 44, 48, 149, 153, 165]}]

        Note: The derived class must implement this method.

        Returns:
          A list of dictionaries as described above
        """
        raise NotImplementedError

    def get_supported_modes(self):
        """Returns a list of dictionaries describing the supported modes.

        Example: returned is a dictionary of band and a list of modes. The band
                 and modes objects returned must be one of those defined in the
                 __init___ of this class.

        supported_modes = [{'band' : self.band_2GHz,
                            'modes' : [mode_b, mode_b | mode_g]},
                           {'band' : self.band_5ghz,
                            'modes' : [mode_a, mode_n, mode_a | mode_n]}]

        Note: The derived class must implement this method.

        Returns:
          A list of dictionaries as described above
        """
        raise NotImplementedError

    def is_security_mode_supported(self, security_mode):
        """Returns if a given security_type is supported.

        Note: The derived class must implement this method.

        Args:
          security_mode: one of the following modes: self.security_disabled,
                         self.security_wep, self.security_wpapsk,
                         self.security_wpa2psk, self.security_wpa8021x,
                         or self.security_wpa28021x

        Returns:
          True if the security mode provided is supported; False otherwise.
        """
        raise NotImplementedError

    def navigate_to_page(self, page_number):
        """Navigates to the page corresponding to the given page number.

        This method performs the translation between a page number and a url to
        load. This is used internally by apply_settings.

        Note: The derived class must implement this method.

        Args:
          page_number: Page number of the page to load
        """
        raise NotImplementedError

    def save_page(self, page_number):
        """Saves the given page.

        Note: The derived class must implement this method.

        Args:
          page_number: Page number of the page to save.
        """
        raise NotImplementedError

    def set_mode(self, mode, band=None):
        """Sets the mode.

        Note: The derived class must implement this method.

        Args:
          mode: must be one of the modes listed in __init__()
          band: the band to select
        """
        raise NotImplementedError

    def set_radio(self, enabled=True):
        """Turns the radio on and off.

        Note: The derived class must implement this method.

        Args:
          enabled: True to turn on the radio; False otherwise
        """
        raise NotImplementedError

    def set_ssid(self, ssid):
        """Sets the SSID of the wireless network.

        Note: The derived class must implement this method.

        Args:
          ssid: Name of the wireless network
        """
        raise NotImplementedError

    def set_channel(self, channel):
        """Sets the channel of the wireless network.

        Note: The derived class must implement this method.

        Args:
          channel: Integer value of the channel
        """
        raise NotImplementedError

    def set_band(self, band):
        """Sets the band of the wireless network.

        Currently there are only two possible values for band: 2kGHz and 5kGHz.
        Note: The derived class must implement this method.

        Args:
          band: Constant describing the band type
        """
        raise NotImplementedError

    def set_security_disabled(self):
        """Disables the security of the wireless network.

        Note: The derived class must implement this method.
        """
        raise NotImplementedError

    def set_security_wep(self, key_value, authentication):
        """Enabled WEP security for the wireless network.

        Note: The derived class must implement this method.

        Args:
          key_value: encryption key to use
          authentication: one of two supported authentication types:
                          wep_authentication_open or wep_authentication_shared
        """
        raise NotImplementedError

    def set_security_wpapsk(self, shared_key, update_interval=1800):
        """Enabled WPA using a private security key for the wireless network.

        Note: The derived class must implement this method.

        Args:
          shared_key: shared encryption key to use
          update_interval: number of seconds to wait before updating
        """
        raise NotImplementedError

    def set_visibility(self, visible=True):
        """Set the visibility of the wireless network.

        Note: The derived class must implement this method.

        Args:
          visible: True for visible; False otherwise
        """
        raise NotImplementedError

    def apply_settings(self):
        """Apply all settings to the access point."""
        # Load the Auth extension
        extension_path = os.path.join(os.path.dirname(__file__),
                                      'basic_auth_extension.crx')
        f = open(extension_path, 'rb')
        base64_extensions = []
        base64_ext = (binascii.b2a_base64(f.read()).strip())
        base64_extensions.append(base64_ext)
        f.close()
        # Connect to the browser
        try:
            self.driver = webdriver.Remote('http://127.0.0.1:9515',
                {'chrome.extensions': base64_extensions})
        except Exception, e:
            raise RuntimeError('Could not connect to webdriver, have you '
                               'downloaded the prebuild components to the /tmp '
                               'directory in the chroot?  Have you run: '
                               '(outside-chroot) <path to chroot tmp directory>'
                               '/chromium-webdriver-parts/.chromedriver?\n'
                               'Exception message: %s' % str(e))
        self.wait = WebDriverWait(self.driver, timeout=5)
        # Pull items by page and then sort
        if self.get_number_of_pages() == -1:
            self.fail(msg='Number of pages is not set.')
        page_range = range(1, self.get_number_of_pages() + 1)
        for i in page_range:
            page_commands = [x for x in self._command_list if x['page'] == i]
            sorted_page_commands = sorted(page_commands,
                                          key=lambda k: k['priority'])
            if sorted_page_commands:
                self.navigate_to_page(i)
                for command in sorted_page_commands:
                    command['method'](*command['args'])
                self.save_page(i)
        self._command_list = []
        self.driver.close()
