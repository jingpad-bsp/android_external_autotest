# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import pprint
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.client.common_lib.cros.network import xmlrpc_security_types
from autotest_lib.server.cros.chaos_ap_configurators import ap_cartridge
from autotest_lib.server.cros.chaos_ap_configurators import \
    ap_configurator_config
from autotest_lib.server.cros.chaos_ap_configurators.static_ap_configurator \
    import StaticAPConfigurator
from autotest_lib.server.cros.chaos_config import ChaosAP
from autotest_lib.server.cros.network import wifi_client


class WiFiChaosConnectionTest(object):
    """Base class for simple (connect/disconnect) dynamic Chaos test."""

    PSK = 'psk'
    FAILED_CONFIG_MSG = 'AP Configuration Failed!'
    TEST_PROFILE_NAME = 'test'


    @property
    def psk_password(self):
        """@returns PSK password."""
        return self._psk_password


    @psk_password.setter
    def psk_password(self, password):
        """Sets PSK password.

        @param password: a string, PSK password.
        """
        self._psk_password = password


    def __init__(self, host, capturer):
        """Initialize.

        @param host: an Autotest host object, device under test (DUT).
        @param capturer: a LinuxSystem object to use to collect packet captures.
        """
        self.client = wifi_client.WiFiClient(host, './debug')
        self._capturer = capturer
        self.error_list = []
        self.ap_config = ap_configurator_config.APConfiguratorConfig()
        self.psk_password = ''

        # Test on channel 5 for 2.4GHz band and channel 48 for 5GHz band.
        # TODO(tgao): support user-specified channel.
        self.band_channel_map = {self.ap_config.BAND_2GHZ: 5,
                                 self.ap_config.BAND_5GHZ: 48}


    def __repr__(self):
        """@returns class name, DUT name + MAC addr and packet tracer name."""
        return 'class: %s, DUT: %s (MAC addr: %s), capturer: %s' % (
                self.__class__.__name__,
                self.client.host.hostname,
                self.client.wifi_mac,
                self._capturer.host.hostname)


    def run_connect_disconnect_test(self, ap_info, log_dir, pcap_file_pattern):
        """Attempts to connect to an AP.

        @param ap_info: a dict of attributes of a specific AP.
        @param log_dir: string path to directory to save pcap in.
        @param pcap_file_pattern: string name of file to save pcap in,
                with one %s which we'll replace with 'success' or 'failure'
                depending on the results of the connection attempt.

        @return a string (error message) or None.

        """
        self.client.shill.disconnect(ap_info['ssid'])
        self.client.shill.clean_profiles()
        # Be extra sure that we're going to push successfully.
        self.client.shill.remove_profile(self.TEST_PROFILE_NAME)
        if (not self.client.shill.create_profile(self.TEST_PROFILE_NAME) or
                not self.client.shill.push_profile(self.TEST_PROFILE_NAME)):
            return 'Failed to set up isolated test context profile.'

        # TODO(wiley) We probably don't always want HT40, but
        #             this information is hard to infer here.
        #             Change how AP configuration happens so that
        #             we expose this.
        self._capturer.start_capture(ap_info['frequency'], ht_type='HT40+')
        try:
            success = False
            if ap_info['security'] == self.PSK:
                security_config = xmlrpc_security_types.WPAConfig(
                        psk=ap_info[self.PSK])
            elif ap_info['security'] == '':
                security_config = xmlrpc_security_types.SecurityConfig()
            else:
                raise error.TestFail('Router has unknown security type: %r' %
                                     ap_info['security'])
            assoc_params = xmlrpc_datatypes.AssociationParameters(
                    ssid=ap_info['ssid'],
                    is_hidden=ap_info['visibility'],
                    security_config=security_config)
            assoc_result = xmlrpc_datatypes.deserialize(
                    self.client.shill.connect_wifi(assoc_params))
            success = assoc_result.success
            if not success:
                return assoc_result.failure_reason
        finally:
            filename = pcap_file_pattern % ('success' if success else 'fail')
            self._capturer.stop_capture(save_dir=log_dir,
                                        save_filename=filename)
            self.client.shill.disconnect(ap_info['ssid'])
            self.client.shill.clean_profiles()
        return None


    def run_ap_test(self, ap_info, tries, log_dir):
        """Runs test on a configured AP.

        @param ap_info: a dict of attributes of a specific AP.
        @param tries: an integer, number of connection attempts.
        @param log_dir: a string, directory to store test logs.
        """

        ap_info['failed_iterations'] = []
        # Check the AP was successfully configured
        if not ap_info['configurator'].get_configuration_success():
            ap_info['failed_iterations'].append(
                {'error': self.FAILED_CONFIG_MSG,
                 'try': 0})
            self.error_list.append(ap_info)
            # Capture screenshot when configuration fails
            screenshots = ap_info['configurator'].get_all_screenshots()
            for (i, image) in enumerate(screenshots):
                screenshot_path = os.path.join(log_dir,
                    'config_error_screenshot_%d.png' % i)
                with open(screenshot_path, 'wb') as f:
                    f.write(image.decode('base64'))
            return

        # Make iteration 1-indexed
        for iteration in range(1, tries+1):
            logging.info('Connection try %d', iteration)
            pcap_file_pattern = '_'.join(['connect_try', str(iteration),
                                          '%s.trc'])
            resp = self.run_connect_disconnect_test(
                    ap_info, log_dir, pcap_file_pattern)
            if resp:
                ap_info['failed_iterations'].append({'error': resp,
                                                     'try': iteration})

        if ap_info['failed_iterations']:
            self.error_list.append(ap_info)


    def _config_one_ap(self, ap, band, security, mode, visibility):
        """Configures an AP for the test.

        @param ap: an APConfigurator object.
        @param band: a string, 2.4GHz or 5GHz.
        @param security: a string, AP security method.
        @param mode: a hexadecimal, 802.11 mode.
        @param visibility: a boolean

        @returns a dict representing one band of a configured AP.
        """
        # Setting the band gets you the bss
        ap.set_band(band)
        # Remove all white space from the ssid
        sanitized_short_name = ap.get_router_short_name().replace(' ', '_')
        ssid = '_'.join([sanitized_short_name,
                         str(self.band_channel_map[band]),
                         str(band).replace('.', '_')])

        ap.power_up_router()
        ap.set_channel(self.band_channel_map[band])
        ap.set_radio(enabled=True)
        ap.set_ssid(ssid)
        if ap.is_visibility_supported():
            ap.set_visibility(visible=visibility)

        ap.set_mode(mode)
        if security == self.PSK:
            logging.debug('Use PSK security w/ password %s', self.psk_password)
            ap.set_security_wpapsk(self.psk_password)
        else:  # Testing open system, i.e. security = ''
            ap.set_security_disabled()

        # DO NOT apply_settings() here. Cartridge is used to apply config
        # settings to multiple APs in parallel, see config_aps().

        return {'configurator': ap,
                'bss': ap.get_bss(),
                'band': band,
                'channel': self.band_channel_map[band],
                'frequency': ChaosAP.FREQUENCY_TABLE[
                        self.band_channel_map[band]],
                'radio': True,
                'ssid': ssid,
                'visibility': visibility,
                'security': security,
                self.PSK: self.psk_password,
                'brand': ap.config_data.get_brand(),
                'model': ap.get_router_short_name()}


    def _get_mode_type(self, ap, band):
        """Gets 802.11 mode for ap at band.

        @param ap: an APConfigurator object.
        @param band: a string, 2.4GHz or 5GHz.

        @returns a hexadecimal, 802.11 mode or None.
        """
        for mode in ap.get_supported_modes():
            if mode['band'] == band:
                for mode_type in mode['modes']:
                    if (mode_type & self.ap_config.MODE_N !=
                        self.ap_config.MODE_N):
                        return mode_type


    def _mark_ap_to_unlock(self, ap, band):
        """Checks if an AP can be unlocked after testing on band.

        Assumption: we always test 2.4GHz before 5GHz, enforced in
                    WiFiChaosTest.run() in chaos_interop_test.py

        Rules for unlocking an AP:
         - a single-band ap can be unlocked after testing on 2.4GHz band
         - a dual-band ap can only be unlocked after testing on 5GHz band

        @param band: a string, 2.4GHz or 5GHz.

        @returns a boolean True == OK to unlock AP after testing on band.
        """
        supported_bands = ap.get_supported_bands()
        bands_supported = [d['band'] for d in supported_bands]
        if band in bands_supported:
            if len(bands_supported) == 1 or band == self.ap_config.BAND_5GHZ:
                return True
        return False


    def config_aps(self, aps, band, security='', visibility=True):
        """Configures a list of APs.

        @param aps: a list of APConfigurator objects.
        @param band: a string, 2.4GHz or 5GHz.
        @param security: a string, AP security method. Defaults to empty string
                         (i.e. open system). Other possible value is self.PSK.
        @param visibility: a boolean.  Defaults to True.

        @returns a list of dicts, each a return by _config_one_ap().
        """
        configured_aps = []
        scan_list = []
        cartridge = ap_cartridge.APCartridge()
        for ap in aps:
            if not ap.is_band_and_channel_supported(
                    band, self.band_channel_map[band]):
                logging.info('Skip %s: band %s and channel %d not supported',
                             ap.get_router_name(), band,
                             self.band_channel_map[band])
                continue

            if isinstance(ap, StaticAPConfigurator):
                configured_aps.append({'configurator': ap,
                        'bss': ap.config_data.get_bss(),
                        'band': band,
                        'channel': ap.config_data.get_channel(),
                        'frequency': ap.config_data.get_frequency(),
                        'radio': True,
                        'ssid': ap.config_data.get_ssid(),
                        'visibility': visibility,
                        'security': ap.config_data.get_security(),
                        self.PSK: ap.config_data.get_psk(),
                        'brand': ap.config_data.get_brand(),
                        'model': ap.get_router_short_name(),
                        'ok_to_unlock': False,})
                continue

            logging.info('Configuring AP %s', ap.get_router_name())
            mode = self._get_mode_type(ap, band)
            ap_info = self._config_one_ap(ap, band, security, mode, visibility)
            ap_info['ok_to_unlock'] = self._mark_ap_to_unlock(ap, band)
            configured_aps.append(ap_info)
            cartridge.push_configurator(ap)
            scan_list.append(ap)
        # Apply config settings to multiple APs in parallel.
        cartridge.run_configurators()
        # iw mlan0 scan for ARM and iw wlan0 scan for x86
        scan_bss = '%s %s scan' % (self.client.command_iw, self.client.wifi_if)
        start_time = int(time.time())
        # Setting 300s as timeout
        logging.info('Waiting for the DUT to find BSS... ')
        while (int(time.time()) - start_time) < 300 and len(scan_list):
           # If command failed: Device or resource busy (-16), run again.
           scan_result = self.client.host.run(scan_bss, ignore_status=True)
           if 'busy' in str(scan_result):
               continue
           for ap in scan_list:
               # If configuration failed, do not wait for the bss.
               if not ap.get_configuration_success():
                   scan_list.remove(ap)
                   continue
               bss = ap.get_bss()
               if bss in str(scan_result):
                   # Remove ap from list if we found bss in scan
                   logging.debug('Found bss %s in scan', bss)
                   scan_list.remove(ap)
               else:
                   continue
        if len(scan_list):
            logging.error('These APs were not listed in scan:')
            for ap_info in configured_aps:
                if ap_info['configurator'] in scan_list:
                    logging.error('Brand:%s\n\tModel:%s\n\tSSID:%s\n'
                                  '\tBSS:%s'.expandtabs(16),
                                   ap_info['brand'], ap_info['model'],
                                   ap_info['ssid'], ap_info['bss'])
                    ap_info['configurator'].reset_command_list()
        return configured_aps


    def power_down(self, ap):
        """Powers down ap.

        @param ap: an APConfigurator object.
        """
        self.power_down_aps([ap])


    def power_down_aps(self, aps):
        """Powers down a list of aps.

        @param aps: a list of APConfigurator objects.
        """
        cartridge = ap_cartridge.APCartridge()
        for ap in aps:
            ap.power_down_router()
            cartridge.push_configurator(ap)
        cartridge.run_configurators()


    def check_test_error(self):
        """Checks if any intermediate test failed.

        @raises TestError: if the AP could not be configured
        @raises TestFail: if self.error_list is not empty and
                          the AP was configured.
        """
        if len(self.error_list) == 0:
            return

        failures = self.error_list[0]['failed_iterations']
        config_failure = False

        if failures[0]['error'] == self.FAILED_CONFIG_MSG:
            config_failure = True

        if config_failure:
            msg = ('\nThe AP was not configured correctly, '
                   'see the ERROR log for more info.\n')
        else:
            msg = '\nFailed with the following errors:\n'

        msg += pprint.pformat(self.error_list)
        # This is shared across tests; reset for the next AP.
        self.error_list = []

        if config_failure:
            raise error.TestError(msg)
        else:
            raise error.TestFail(msg)


    def run_once(self, tries=1):
        """Main entry function for autotest.

        @param tries: an integer, number of connection attempts.
        """
        raise NotImplementedError('Child class must implement this!')
