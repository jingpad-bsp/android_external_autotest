# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import pprint

from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest, test
from autotest_lib.server.cros.chaos_ap_configurators import ap_cartridge
from autotest_lib.server.cros.chaos_ap_configurators import ap_configurator_factory
from autotest_lib.server.cros.chaos_ap_configurators import download_chromium_prebuilt
from autotest_lib.server.cros.chaos_config import ChaosAP
from autotest_lib.server.cros.wlan import connector, disconnector

class network_WiFiSimpleConnectionServer(test.test):
    """ Dynamic Chaos test. """

    version = 1


    def initialize(self, host, capturer=None):
        self.host = host
        self.client_at = autotest.Autotest(self.host)
        self.c = connector.TracingConnector(self.host, capturer)
        self.d = disconnector.Disconnector(self.host)
        self.error_list = []


    def run_connect_disconnect_test(self, ap_info, iteration):
        """ Connects to the AP and Navigates to URL.

        @param ap_info: a dict of attributes of a specific AP.
        @param iteration: an integer, 1-indexed current iteration.

        @return None if there are no errors.
                The error messages if there are any errors.
        """
        error = None

        ssid = ap_info['ssid']
        frequency = ap_info['frequency']
        bss = ap_info['bss']

        self.d.disconnect(ssid)
        self.c.set_frequency(frequency)
        log_folder = os.path.join(self.outputdir, '%s' % bss)
        if not os.path.exists(log_folder):
            os.mkdir(log_folder)
        self.c.set_filename(
            os.path.join(log_folder, 'connect_try_%d' % iteration))
        error = None
        try:
            self.c.connect(ssid, frequency=frequency)
        except (connector.ConnectException,
                connector.ConnectFailed,
                connector.ConnectTimeout) as e:
            error = 'Failed to connect'
        finally:
            self.d.disconnect(ssid)
        return error


    def supported_band_and_channel(self, ap, band, channel):
        """ Checks if specified band and channel is supported by ap.

        @param ap: an APConfigurable object.
        @param band: a string.
        @param channel: a string.
        """
        bands = ap.get_supported_bands()
        for current_band in bands:
            if (current_band['band'] == band and
                channel in current_band['channels']):
                return True
        return False


    def _run_ap_test(self, ap_info, tries):
        """ Runs test on a configured AP.

        @param ap_info: a dict.
        @param tries: an integer, number of times to connect/disconnect.
        """
        ap_info['failed_iterations'] = []
        for iteration in range(1, tries+1):
            logging.info('Connection try %d', iteration)
            resp = self.run_connect_disconnect_test(ap_info, iteration)
            if resp:
                ap_info['failed_iterations'].append({'error': resp,
                                                     'try': iteration})
        if ap_info['failed_iterations']:
            self.error_list.append(ap_info)


    def _config_ap(self, ap, band, channel):
        """ Configures an AP for the test.

        @param ap: an APConfigurator object.
        @param band: a string, 2.4GHz or 5GHz.
        @param channel: an integer.

        @returns a dict representing one band of a configured AP.
        """
        # Setting the band gets you the bss
        ap.set_band(band)
        ssid = '_'.join([ap.get_router_short_name(),
                         str(channel),
                         str(band).replace('.', '_')])
        logging.info('Using ssid %s', ssid)

        ap.power_up_router()
        ap.set_channel(channel)
        ap.set_radio(enabled=True)
        ap.set_ssid(ssid)
        ap.set_visibility(visible=True)
        # Testing open system, i.e. no security
        ap.set_security_disabled()
        # DO NOT apply_settings() here. Cartridge is used to apply config
        # settings to multiple APs in parallel, see _config_all_aps().

        return {
            'bss': ap.get_bss(),
            'band': band,
            'channel': channel,
            'frequency': ChaosAP.FREQUENCY_TABLE[channel],
            'radio': True,
            'ssid': ssid,
            'visibility': True,
            'security': None,
            }


    def _config_all_aps(self, all_aps):
        """ Configures all APs in Chaos lab.

        @param all_aps: a list of APConfigurator objects, returned by factory.

        @returns a list of dicts, each a return by _config_ap().
        """
        bands = [all_aps[0].band_2ghz, all_aps[0].band_5ghz]
        # TODO(tgao): support passing in channel params?
        channels = [5, 48]
        configured_aps = []

        cartridge = ap_cartridge.APCartridge()
        for ap in all_aps:
            for band, channel in zip(bands, channels):
                if not self.supported_band_and_channel(ap, band, channel):
                    continue
                logging.debug('AP %s supports band %s and channel %s',
                              ap.get_bss(), band, channel)
                ap_info = self._config_ap(ap, band, channel)
                configured_aps.append(ap_info)
                cartridge.push_configurator(ap)

        # Apply config settings to all APs in parallel.
        cartridge.run_configurators()
        return configured_aps


    def _deconfig_all_aps(self, all_aps):
        """ Powers down the APs used for a test run.

        @param all_aps: a list of APConfigurator objects, returned by factory.
        """
        cartridge = ap_cartridge.APCartridge()
        for ap in all_aps:
            ap.power_down_router()
            cartridge.push_configurator(ap)

        cartridge.run_configurators()


    def run_once(self, tries=1):
        """ Entry point of this test.

        @param tries: an integer, number of times to connect/disconnect.
        """
        if download_chromium_prebuilt.download_chromium_prebuilt_binaries():
            raise error.TestError('The binaries were just downloaded.  Please '
                                  'run: (outside-chroot) <path to chroot tmp '
                                  'directory>/ %s./ chromedriver'
                                  % download_chromium_prebuilt.DOWNLOAD_PATH)
        # Install all of the autotest libriaries on the client
        self.client_at.install()
        factory = ap_configurator_factory.APConfiguratorFactory()
        all_aps = factory.get_ap_configurators()
        configured_aps = self._config_all_aps(all_aps)
        for ap_info in configured_aps:
            self._run_ap_test(ap_info, tries)

        logging.info('Client test complete, powering down routers.')
        self._deconfig_all_aps(all_aps)

        # Test failed if any of the intermediate tests failed.
        if self.error_list:
            msg = 'Failed with the following AP\'s:\n'
            msg += pprint.pformat(self.error_list)
            raise error.TestFail(msg)
