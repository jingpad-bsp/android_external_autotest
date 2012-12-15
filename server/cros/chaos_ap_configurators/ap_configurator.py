# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import binascii
import copy
import logging
import os
import sys
import xmlrpclib

import web_driver_core_helpers

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'deps',
                             'chrome_test', 'test_src', 'third_party',
                             'webdriver', 'pylib'))

try:
  from selenium import webdriver
except ImportError:
  raise ImportError('Could not locate the webdriver package.  Did you build? '
                    'Are you using a prebuilt autotest package?')

from selenium.common.exceptions import TimeoutException as \
    SeleniumTimeoutException
from selenium.webdriver.support.ui import WebDriverWait


class APConfigurator(web_driver_core_helpers.WebDriverCoreHelpers):
    """Base class for objects to configure access points using webdriver."""

    def __init__(self, ap):
        super(APConfigurator, self).__init__()
        self.rpm_client = xmlrpclib.ServerProxy(
            'http://chromeos-rpmserver1.cbf.corp.google.com:9999',
            verbose=False)

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

        self.admin_interface_url = ap.get_admin()
        self.class_name = ap.get_class()
        self.short_name = ap.get_model()
        self.mac_address = ap.get_wan_mac()
        self.device_name = '%s %s' % (ap.get_brand(), ap.get_model())

        self._command_list = []

    def __del__(self):
        try:
            self.driver.close()
        except:
            pass

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
        return ('Router name: %s, Controller class: %s, MAC '
                'Address: %s' % (self.short_name, self.class_name,
                                 self.mac_address))

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

    def _get_channel_popup_position(self, channel):
        """Internal method that converts a channel value to a popup position."""
        supported_bands = self.get_supported_bands()
        for band in supported_bands:
            if band['band'] == self.current_band:
                return band['channels'].index(channel)
        raise RuntimeError('The channel passed %d to the band %s is not '
                           'supported.' % (channel, band))

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

    def power_cycle_router_up(self):
        """Turns the ap off and then back on again."""
        self.rpm_client.queue_request(self.device_name, 'CYCLE')

    def power_down_router(self):
        """Turns off the power to the ap via the power strip."""
        self.rpm_client.queue_request(self.device_name, 'OFF')

    def power_up_router(self):
        """Turns on the power to the ap via the power strip.

        This method returns once it can navigate to a web page of the ap UI.
        """
        self.rpm_client.queue_request(self.device_name, 'ON')
        self.establish_driver_connection()
        self.wait = WebDriverWait(self.driver, timeout=5)
        # With the 5 second timeout give the router up to 2 minutes
        for i in range(24):
            try:
                self.navigate_to_page(1)
                logging.debug('Page navigation complete')
                return
            # Navigate to page may throw a Selemium error or its own
            # RuntimeError depending on the implementation.  Either way we are
            # bringing a router back from power off, we need to be patient.
            except:
                self.driver.refresh()
                logging.info('Waiting for router %s to come back up.' %
                             self.get_router_name())
        raise RuntimeError('Unable to load admin page after powering on the '
                           'router: %s' % self.get_router_name)

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

    def establish_driver_connection(self):
        # Load the Auth extension
        extension_path = os.path.join(os.path.dirname(__file__),
                                      'basic_auth_extension.crx')
        f = open(extension_path, 'rb')
        base64_extensions = []
        base64_ext = (binascii.b2a_base64(f.read()).strip())
        base64_extensions.append(base64_ext)
        f.close()
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

    def apply_settings(self):
        """Apply all settings to the access point."""
        self.establish_driver_connection()
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
