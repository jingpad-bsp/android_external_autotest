# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server.cros.chaos_ap_configurators import ap_spec

class APConfigurator():
    """Base class to find and control access points."""


    def __init__(self, ap_config=None):
        """Construct an APConfigurator.

        @param ap_config: information from the configuration file

        """
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
        self._ssid = None

        # Diagnostic members
        self._command_list = []
        self._screenshot_list = []
        self._traceback = None

        self.driver_connection_established = False
        self.router_on = False
        self.configuration_success = False


    @staticmethod
    def is_dynamic():
        """
        Test for dynamically configurable AP

        @return bool

        """
        return False


    @property
    def ssid(self):
        """Returns the SSID."""
        return self._ssid


    def save_screenshot(self):
        """
        Stores and returns the screenshot as a base 64 encoded string.
        Note: The derived class may override this method.

        @returns the screenshot as a base 64 encoded string; if there was
        an error saving the screenshot None is returned.

        """
        logging.warning('%s.%s: apparently not needed',
                self.__class__.__name__,
                self.save_screenshot.__name__)
        return None


    @property
    def traceback(self):
        """
        Returns the traceback of a configuration error as a string.

        Note that if get_configuration_success returns True this will
        be none.

        """
        return self._traceback


    @traceback.setter
    def traceback(self, value):
        """
        Set the traceback.

        If the APConfigurator crashes use this to store what the traceback
        was as a string.  It can be used later to debug configurator errors.

        @param value: a string representation of the exception traceback

        """
        self._traceback = value


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



    def set_using_ap_spec(self, set_ap_spec, power_up=True):
        """
        Sets all configurator options.
        Note: The derived class may override this method.

        @param set_ap_spec: APSpec object
        @param power_up: bool, enable power via rpm if applicable

        """
        logging.warning('%s.%s: Not Implemented',
                self.__class__.__name__,
                self.set_using_ap_spec.__name__)


    def apply_settings(self):
        """
        Apply all settings to the access point.
        Note: The derived class may override this method.

        """
        logging.warning('%s.%s: Not Implemented',
                self.__class__.__name__,
                self.apply_settings.__name__)
