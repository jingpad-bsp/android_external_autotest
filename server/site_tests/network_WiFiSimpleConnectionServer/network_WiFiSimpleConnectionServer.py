# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import pprint

from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest, test
from autotest_lib.server.cros.chaos_ap_configurators import ap_configurator_factory
from autotest_lib.server.cros.chaos_ap_configurators import download_chromium_prebuilt
from autotest_lib.server.cros.chaos_ap_configurators import ap_cartridge
from autotest_lib.server.cros.chaos_config import ChaosAP
from autotest_lib.server.cros.wlan import connector, disconnector

class network_WiFiSimpleConnectionServer(test.test):

    version = 1


    def initialize(self, host, capturer=None):
        self.host = host
        self.client_at = autotest.Autotest(self.host)
        self.c = connector.TracingConnector(self.host, capturer)
        self.d = disconnector.Disconnector(self.host)
        self.error_list = []


    def run_connect_disconnect_test(self, ap, iteration):
        """ Connects to the AP and Navigates to URL.

        Args:
            ap: the ap object
            iteration: the current iteration

        Returns:
            None if there are no errors
            The error messages if there are any errors.
        """
        error = None

        ssid = ap['ssid']
        frequency = ap['frequency']
        bss = ap['bss']

        self.d.disconnect(ssid)
        self.c.set_frequency(frequency)
        log_folder = os.path.join(self.outputdir, '%s' % bss)
        if not os.path.exists(log_folder):
            os.mkdir(log_folder)
        self.c.set_filename(os.path.join(log_folder, 'connect_try_%d'
                                         % (iteration+1)))
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
        bands = ap.get_supported_bands()
        for current_band in bands:
            if (current_band['band'] == band and
                channel in current_band['channels']):
                return True
        return False


    def loop_ap_configs_and_test(self, all_aps, tries):
        """ Configures AP to all supported radio permuations runs a test.

        Args:
            ap: List of APs to run the test on.
            tries: The number of times to connect/disconnect.
        """
        # We need to go through the APs and pull out the common bands and
        # then channels, the factory can do this a better way.

        bands_and_channels = {}
        for ap in all_aps:
            bands = ap.get_supported_bands()
            for band in bands:
                if band['band'] not in bands_and_channels:
                    bands_and_channels[band['band']] = set(band['channels'])
                else:
                    bands_and_channels[band['band']].union(band['channels'])

        bands = [all_aps[0].band_2ghz, all_aps[0].band_5ghz]
        channels = [5, 48]
        cartridge = ap_cartridge.APCartridge()
        for band, channel in zip(bands, channels):
            logging.info('Testing band %s and channel %s' % (band, channel))
            configured_aps = []
            for ap in all_aps:
                if self.supported_band_and_channel(ap, band, channel):
                    # Setting the band gets you the bss
                    ap.set_band(band)
                    ap_info = {
                        'bss': ap.get_bss(),
                        'band': band,
                        'channel': channel,
                        'frequency': ChaosAP.FREQUENCY_TABLE[channel],
                        'radio': True,
                        'ssid': '_'.join([ap.get_router_short_name(),
                                          str(channel),
                                          str(band).replace('.', '_')]),
                        'visibility': True,
                        'security': None,
                    }

                    logging.info('Using ssid %s', ap_info['ssid'])
                    ap.power_up_router()
                    ap.set_channel(ap_info['channel'])
                    ap.set_radio(enabled=ap_info['radio'])
                    ap.set_ssid(ap_info['ssid'])
                    ap.set_visibility(visible=ap_info['visibility'])
                    ap.set_security_disabled()
                    configured_aps.append(ap_info)
                    cartridge.push_configurator(ap)
            cartridge.run_configurators()

            for ap in configured_aps:
                logging.info('Client connecting to ssid %s' % ap['ssid'])
                ap_info['failed_iterations'] = []
                failure = False
                for iteration in range(tries):
                    logging.info('Connection try %d' % (iteration + 1))
                    resp = self.run_connect_disconnect_test(ap, iteration)
                    if resp:
                        failure = True
                        ap_info['failed_connections'].append({'error': resp,
                                                             'try': iteration})
                if failure:
                    self.error_list.append(ap_info)


    def run_once(self, tries=1):
        if download_chromium_prebuilt.download_chromium_prebuilt_binaries():
            raise error.TestError('The binaries were just downloaded.  Please '
                                  'run: (outside-chroot) <path to chroot tmp '
                                  'directory>/ %s./ chromedriver'
                                  % download_chromium_prebuilt.DOWNLOAD_PATH)
        # Install all of the autotest libriaries on the client
        self.client_at.install()
        factory = ap_configurator_factory.APConfiguratorFactory()
        all_aps = factory.get_ap_configurators()
        self.loop_ap_configs_and_test(all_aps, tries)
        logging.info('Client test complete, powering down router')
        for ap in all_aps:
            ap.power_down_router()
            ap.apply_settings()

        # Test failed if any of the intermediate tests failed.
        if self.error_list:
            msg = 'Failed with the following AP\'s:\n'
            msg += pprint.pformat(self.error_list)
            raise error.TestFail(msg)
