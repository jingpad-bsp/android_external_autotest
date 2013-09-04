# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import binascii
import copy
import logging
import os
import sys
import xmlrpclib

import ap_spec
import download_chromium_prebuilt
import web_driver_core_helpers

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'deps',
                             'chrome_test', 'test_src', 'third_party',
                             'webdriver', 'pylib'))

try:
  from selenium import webdriver
except ImportError:
  raise ImportError('Could not locate the webdriver package.  Did you build? '
                    'Are you using a prebuilt autotest package?')


class APConfigurator(web_driver_core_helpers.WebDriverCoreHelpers):
    """Base class for objects to configure access points using webdriver."""


    def __init__(self, ap_config=None, set_ap_spec=None):
        """Construct an APConfigurator.

        @param ap_config: information from the configuration file
        @param set_ap_spec: APSpec object that when passed will set all
                            of the configuration options
        """
        super(APConfigurator, self).__init__()
        self.rpm_client = xmlrpclib.ServerProxy(
            'http://chromeos-rpmserver1.cbf.corp.google.com:9999',
            verbose=False)

        if ap_config:
            # Load the data for the config file
            self.admin_interface_url = ap_config.get_admin()
            self.class_name = ap_config.get_class()
            self.short_name = ap_config.get_model()
            self.mac_address = ap_config.get_wan_mac()
            self.host_name = ap_config.get_wan_host()
            self.config_data = ap_config

        # Set a default band, this can be overriden by the subclasses
        self.current_band = ap_spec.BAND_2GHZ

        self._command_list = []
        self._screenshot_list = []

        self.driver_connection_established = False
        self.router_on = False
        self.configuration_success = False

        self.ap_spec = set_ap_spec
        if self.ap_spec:
            self.set_using_ap_spec(self.ap_spec)


    def __del__(self):
        try:
            self.driver.close()
        except:
            pass


    def add_item_to_command_list(self, method, args, page, priority):
        """
        Adds commands to be executed against the AP web UI.

        @param method: the method to run
        @param args: the arguments for the method you want executed
        @param page: the page on the web ui where to run the method against
        @param priority: the priority of the method
        """
        self._command_list.append({'method': method,
                                   'args': copy.copy(args),
                                   'page': page,
                                   'priority': priority})


    def reset_command_list(self):
        """Resets all internal command state."""
        logging.error('Dumping command list %s', self._command_list)
        self.configuration_success = False
        self._command_list = []
        self.destroy_driver_connection()


    @property
    def screenshot_list(self):
        """Returns the file as a base 64 encoded string for screenshot."""
        if self.driver_connection_established:
            try:
                screenshot = self.driver.get_screenshot_as_base64()
            except:
                logging.error('Getting the screenshot failed.')
                screenshot = None
            if screenshot:
                self._screenshot_list.append(screenshot)
        return self._screenshot_list
        self._screenshot_list = []


    def get_router_name(self):
        """Returns a string to describe the router."""
        return ('Router name: %s, Controller class: %s, MAC '
                'Address: %s' % (self.short_name, self.class_name,
                                 self.mac_address))


    def get_configuration_success(self):
        """Returns True if the configuration was a success; False otherwise"""
        return self.configuration_success


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
                           {'band' : ap_spec.BAND_5GHZ,
                            'channels' : [26, 40, 44, 48, 149, 153, 165]}]

        Note: The derived class must implement this method.

        @return a list of dictionaries as described above
        """
        raise NotImplementedError


    def get_bss(self):
        """Returns the bss of the AP."""
        if self.current_band == ap_spec.BAND_2GHZ:
            return self.config_data.get_bss()
        else:
            return self.config_data.get_bss5()


    def _get_channel_popup_position(self, channel):
        """Internal method that converts a channel value to a popup position."""
        supported_bands = self.get_supported_bands()
        for band in supported_bands:
            if band['band'] == self.current_band:
                return band['channels'].index(channel)
        raise RuntimeError('The channel passed %d to the band %s is not '
                           'supported.' % (channel, band))


    def get_supported_modes(self):
        """
        Returns a list of dictionaries describing the supported modes.

        Example: returned is a dictionary of band and a list of modes. The band
                 and modes objects returned must be one of those defined in the
                 __init___ of this class.

        supported_modes = [{'band' : self.band_2GHz,
                            'modes' : [mode_b, mode_b | mode_g]},
                           {'band' : ap_spec.BAND_5GHZ,
                            'modes' : [mode_a, mode_n, mode_a | mode_n]}]

        Note: The derived class must implement this method.

        @return a list of dictionaries as described above
        """
        raise NotImplementedError


    def is_visibility_supported(self):
        """
        Returns if AP supports setting the visibility (SSID broadcast).

        @return True if supported; False otherwise.
        """
        return True


    def is_band_and_channel_supported(self, band, channel):
        """
        Returns if a given band and channel are supported.

        @param band: the band to check if supported
        @param channel: the channel to check if supported

        @return True if combination is supported; False otherwise.
        """
        bands = self.get_supported_bands()
        for current_band in bands:
            if (current_band['band'] == band and
                channel in current_band['channels']):
                return True
        return False


    def is_security_mode_supported(self, security_mode):
        """
        Returns if a given security_type is supported.

        Note: The derived class must implement this method.

        @param security_mode: one of the following modes:
                         self.security_disabled,
                         self.security_wep,
                         self.security_wpapsk,
                         self.security_wpa2psk

        @return True if the security mode is supported; False otherwise.
        """
        raise NotImplementedError


    def navigate_to_page(self, page_number):
        """
        Navigates to the page corresponding to the given page number.

        This method performs the translation between a page number and a url to
        load. This is used internally by apply_settings.

        Note: The derived class must implement this method.

        @param page_number: page number of the page to load
        """
        raise NotImplementedError


    def power_cycle_router_up(self):
        """Queues the power cycle up command."""
        self.add_item_to_command_list(self._power_cycle_router_up, (), 1, 0)


    def _power_cycle_router_up(self):
        """Turns the ap off and then back on again."""
        self.rpm_client.queue_request(self.host_name, 'OFF')
        self.router_on = False
        self._power_up_router()


    def power_down_router(self):
        """Queues up the power down command."""
        self.add_item_to_command_list(self._power_down_router, (), 1, 999)


    def _power_down_router(self):
        """Turns off the power to the ap via the power strip."""
        self.rpm_client.queue_request(self.host_name, 'OFF')
        self.router_on = False


    def power_up_router(self):
        """Queues up the power up command."""
        self.add_item_to_command_list(self._power_up_router, (), 1, 0)


    def _power_up_router(self):
        """
        Turns on the power to the ap via the power strip.

        This method returns once it can navigate to a web page of the ap UI.
        """
        if self.router_on:
            return
        self.rpm_client.queue_request(self.host_name, 'ON')
        self.establish_driver_connection()
        # With the 5 second timeout give the router up to 2 minutes
        for i in range(1,10):
            try:
                self.navigate_to_page(1)
                logging.debug('Page navigation complete')
                self.router_on = True
                return
            # Navigate to page may throw a Selemium error or its own
            # RuntimeError depending on the implementation.  Either way we are
            # bringing a router back from power off, we need to be patient.
            except:
                self.driver.refresh()
                logging.info('Waiting for router %s to come back up.',
                             self.get_router_name())
                # Sometime the APs just don't come up right.
                if i%2 == 0:
                    logging.info('Cannot connect to AP, forcing cycle')
                    self.rpm_client.queue_request(self.host_name, 'CYCLE')
        raise RuntimeError('Unable to load admin page after powering on the '
                           'router: %s' % self.get_router_name())


    def save_page(self, page_number):
        """
        Saves the given page.

        Note: The derived class must implement this method.

        @param page_number: Page number of the page to save.
        """
        raise NotImplementedError


    def set_using_ap_spec(self, set_ap_spec):
        """
        Sets all configurator options.

        @param set_ap_spec: APSpec object
        """
        self.set_ssid(set_ap_spec.ssid)
        if self.is_visibility_supported():
            self.set_visibility(set_ap_spec.visible)
        if (set_ap_spec.security == ap_spec.SECURITY_TYPE_WPAPSK or
            set_ap_spec.security == ap_spec.SECURITY_TYPE_WPA2PSK):
            self.set_security_wpapsk(set_ap_spec.password)
        else:
            self.set_security_disabled()
        self.set_band(set_ap_spec.band)
        self.set_mode(set_ap_spec.mode)
        self.set_channel(set_ap_spec.channel)
        self.ap_spec = set_ap_spec


    def set_mode(self, mode, band=None):
        """
        Sets the mode.

        Note: The derived class must implement this method.

        @param mode: must be one of the modes listed in __init__()
        @param band: the band to select
        """
        raise NotImplementedError


    def set_radio(self, enabled=True):
        """
        Turns the radio on and off.

        Note: The derived class must implement this method.

        @param enabled: True to turn on the radio; False otherwise
        """
        raise NotImplementedError


    def set_ssid(self, ssid):
        """
        Sets the SSID of the wireless network.

        Note: The derived class must implement this method.

        @param ssid: name of the wireless network
        """
        raise NotImplementedError


    def set_channel(self, channel):
        """
        Sets the channel of the wireless network.

        Note: The derived class must implement this method.

        @param channel: integer value of the channel
        """
        raise NotImplementedError


    def set_band(self, band):
        """
        Sets the band of the wireless network.

        Currently there are only two possible values for band: 2kGHz and 5kGHz.
        Note: The derived class must implement this method.

        @param band: Constant describing the band type
        """
        raise NotImplementedError


    def set_security_disabled(self):
        """
        Disables the security of the wireless network.

        Note: The derived class must implement this method.
        """
        raise NotImplementedError


    def set_security_wep(self, key_value, authentication):
        """
        Enabled WEP security for the wireless network.

        Note: The derived class must implement this method.

        @param key_value: encryption key to use
        @param authentication: one of two supported WEP authentication types:
                               open or shared.
        """
        raise NotImplementedError


    def set_security_wpapsk(self, shared_key, update_interval=1800):
        """Enabled WPA using a private security key for the wireless network.

        Note: The derived class must implement this method.

        @param shared_key: shared encryption key to use
        @param update_interval: number of seconds to wait before updating
        """
        raise NotImplementedError

    def set_visibility(self, visible=True):
        """Set the visibility of the wireless network.

        Note: The derived class must implement this method.

        @param visible: True for visible; False otherwise
        """
        raise NotImplementedError


    def establish_driver_connection(self):
        """Makes a connection to the webdriver service."""
        if self.driver_connection_established:
            return
        # Load the Auth extension
        webdriver_server = download_chromium_prebuilt.check_webdriver_ready()
        if webdriver_server is None:
            raise RuntimeError('Unable to connect to webdriver locally or '
                               'via the lab service.')
        extension_path = os.path.join(os.path.dirname(__file__),
                                      'basic_auth_extension.crx')
        f = open(extension_path, 'rb')
        base64_extensions = []
        base64_ext = (binascii.b2a_base64(f.read()).strip())
        base64_extensions.append(base64_ext)
        f.close()
        webdriver_url = ('http://%s:9515' % webdriver_server)
        self.driver = webdriver.Remote(webdriver_url,
            {'chrome.extensions': base64_extensions})
        self.driver_connection_established = True


    def destroy_driver_connection(self):
        """Breaks the connection to the webdriver service."""
        try:
            self.driver.close()
        except Exception, e:
            logging.debug('Webdriver is crashed, should be respawned')
        finally:
            self.driver_connection_established = False


    def apply_settings(self):
        """Apply all settings to the access point.

        @param skip_success_validation: Boolean to track if method was
                                        executed successfully.
        """
        self.configuration_success = False
        if len(self._command_list) == 0:
            return

        # If all we are doing is powering down the router, don't mess with
        # starting up webdriver.
        if (len(self._command_list) == 1 and
            self._command_list[0]['method'] == self._power_down_router):
            self._command_list[0]['method'](*self._command_list[0]['args'])
            self._command_list.pop()
            self.destroy_driver_connection()
            return
        self.establish_driver_connection()
        # Pull items by page and then sort
        if self.get_number_of_pages() == -1:
            self.fail(msg='Number of pages is not set.')
        page_range = range(1, self.get_number_of_pages() + 1)
        for i in page_range:
            page_commands = [x for x in self._command_list if x['page'] == i]
            sorted_page_commands = sorted(page_commands,
                                          key=lambda k: k['priority'])
            if sorted_page_commands:
                first_command = sorted_page_commands[0]['method']
                # If the first command is bringing the router up or down,
                # do that before navigating to a URL.
                if (first_command == self._power_up_router or
                    first_command == self._power_cycle_router_up or
                    first_command == self._power_down_router):
                    direction = 'up'
                    if first_command == self._power_down_router:
                        direction = 'down'
                    logging.info('Powering %s %s', direction,
                                 self.get_router_name())
                    first_command(*sorted_page_commands[0]['args'])
                    sorted_page_commands.pop(0)

                # If the router is off, no point in navigating
                if not self.router_on:
                    if len(sorted_page_commands) == 0:
                        # If all that was requested was to power off
                        # the router then abort here and do not set the
                        # configuration_success bit.  The reason is
                        # because if we failed on the configuration that
                        # failure should remain since all tests power
                        # down the AP when they are done.
                        return
                    break

                self.navigate_to_page(i)
                for command in sorted_page_commands:
                    command['method'](*command['args'])
                self.save_page(i)
        self._command_list = []
        self.configuration_success = True
        self.destroy_driver_connection()
