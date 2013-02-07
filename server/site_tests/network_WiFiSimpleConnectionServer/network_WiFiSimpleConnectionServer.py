# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import pprint

from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest, test
from autotest_lib.server.cros.chaos_ap_configurators import ap_configurator_factory
from autotest_lib.server.cros.chaos_ap_configurators import download_chromium_prebuilt
from autotest_lib.server.cros.chaos_ap_configurators import ap_cartridge
from autotest_lib.server.cros.wlan import connector, disconnector

class network_WiFiSimpleConnectionServer(test.test):

    version = 1


    def initialize(self, host):
        self.host = host

        self.c = connector.Connector(self.host)
        self.d = disconnector.Disconnector(self.host)

        self.error_list = []


    def run_connect_disconnect_test(self, ssid, security=None, passphrase=None):
        """ Connects to the AP and Navigates to URL.

        Args:
            ssid: The ssid of the AP to connect.
            security: The security type of the AP to connect.
            passphrase: The passphrase of the AP to connect.

        Returns:
            None if there are no errors
            The error messages if there are any errors.
        """
        error = None

        self.job.set_state('client_passed', None)
        client_at = autotest.Autotest(self.host)

        try:
            self.c.connect(ssid)
        except (connector.ConnectException,
                connector.ConnectFailed,
                connector.ConnectTimeout) as e:
            error = 'Failed to connect'
        finally:
            self.d.disconnect(ssid)

        # Get the state of network_NavigateToUrl after running.
        if not error:
            state = self.job.get_state('client_passed')
            if state is None:
                error = ('The client test did not return a state'
                         'value. Perhaps it did not run.')
            elif state is False:
                error = ('The client failed to load the site.  We may '
                         'have networking issues')
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
                    ap_info = {
                        'band': band,
                        'channel': channel,
                        'radio': True,
                        'ssid': '_'.join([ap.get_router_short_name(),
                                          str(channel),
                                          str(band).replace('.', '_')]),
                        'visibility': True,
                        'security': None,
                    }
                    logging.info('Using ssid %s', ap_info['ssid'])
                    ap.power_up_router()
                    ap.set_band(ap_info['band'])
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
                for iteration in range(tries):
                    logging.info('Connection try %d' % iteration)
                    resp = self.run_connect_disconnect_test(ap['ssid'], tries)
                    if resp:
                        ap_info['error'] = resp
                        ap_info['iterations_before_failure'] = iteration
                        self.error_list.append(ap_info)
                        break


    def run_once(self, tries=1):
        if download_chromium_prebuilt.download_chromium_prebuilt_binaries():
            raise error.TestError('The binaries were just downloaded.  Please '
                                  'run: (outside-chroot) <path to chroot tmp '
                                  'directory>/ %s./ chromedriver'
                                  % download_chromium_prebuilt.DOWNLOAD_PATH)

        factory = ap_configurator_factory.APConfiguratorFactory()
        all_aps = factory.get_ap_configurators()
        self.loop_ap_configs_and_test(all_aps, tries)
        logging.info('Client test complete, powering down router')
        factory.turn_off_all_routers()

        # Test failed if any of the intermediate tests failed.
        if self.error_list:
            msg = 'Failed with the following AP\'s:\n'
            msg += pprint.pformat(self.error_list)
            raise error.TestFail(msg)
