# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import pprint
import shutil
import sys

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

from autotest_lib.server import autotest, test

from autotest_lib.server.cros.chaos_ap_configurators import ap_configurator_factory
from autotest_lib.server.cros.chaos_ap_configurators import download_chromium_prebuilt
from autotest_lib.server.cros.wlan import connector, disconnector
from autotest_lib.server.cros.wlan import profile_manager

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
            client_at.run_test('network_NavigateToUrl', device='wifi')
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


    def loop_ap_configs_and_test(self, ap, tries):
        """ Configures AP to all supported radio permuations runs a test.
        Args:
            ap: The AP to run the test on.
            tries: The number of times to connect/disconnect.
        """
        bands_info = ap.get_supported_bands()
        # For each band, we want to iterate through all possible channels.
        for band, channel in [[band['band'], channel] for band in bands_info
                               for channel in band['channels']]:
            logging.info('Running test using band %s and channel %s',
                         band, channel)
            ap_info = {
                'band': band,
                'channel': channel,
                'radio': True,
                'ssid': '_'.join([ap.get_router_short_name(), str(channel),
                                 str(band)]),
                'visibility': True,
                'security': None,
            }
            logging.info('Using ssid %s', ap_info['ssid'])
            ap.set_band(ap_info['band'])
            ap.set_channel(ap_info['channel'])
            ap.set_radio(enabled=ap_info['radio'])
            ap.set_ssid(ap_info['ssid'])
            ap.set_visibility(visible=ap_info['visibility'])
            ap.set_security_disabled()
            ap.apply_settings()
            for iteration in range(tries):
                resp = self.run_connect_disconnect_test(ap_info['ssid'], tries)
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
        for ap in all_aps:
            ap_name = ap.get_router_short_name()
            logging.debug('Turning on ap: %s' % ap_name)
            ap.power_up_router()

            try:
                self.loop_ap_configs_and_test(ap, tries)
            finally:
                logging.debug('Client test complete, powering down router')
                ap.power_down_router()

        # Test failed if any of the intermediate tests failed.
        if self.error_list:
            msg = 'Failed with the following AP\'s:\n'
            msg += pprint.pformat(self.error_list)
            raise error.TestFail(msg)
