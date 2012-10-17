# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import shutil
import sys

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.server import test, autotest
from autotest_lib.client.cros.wifi_compat import ap_configurator_factory
from autotest_lib.client.cros.wifi_compat import download_chromium_prebuilt

class network_WiFiSimpleConnectionServer(test.test):
    version = 1

    def _run_client_test(self, ssid):
        client_at = autotest.Autotest(self.client)
        self.job.set_state('client_passed', None)
        client_at.run_test('network_WiFiSimpleConnection', ssid=ssid)
        state = self.job.get_state('client_passed')
        if state is None:
            raise error.TestError('The client test did not return a state'
                                  'value. Perhaps it did not run.')
        elif state is False:
            raise error.TestFail('The client test to connect to a network with '
                                 'ssid of %s failed.  See the client test logs '
                                 'for more information.' % ssid)


    def run_once(self, host=None):
        self.client = host
        if download_chromium_prebuilt.download_chromium_prebuilt_binaries():
            raise error.TestError('The binaries were just downloaded.  Please '
                                  'run: (outside-chroot) <path to chroot tmp '
                                  'directory>/ %s./ chromedriver'
                                  % download_chromium_prebuilt.DOWNLOAD_PATH)

        config_file = os.path.join(self.job.configdir, 'wifi_compat_config')
        logging.debug('building the factory object')
        factory = ap_configurator_factory.APConfiguratorFactory(config_file)
        logging.debug('turing off routers')
        factory.turn_off_all_routers()
        all_aps = factory.get_ap_configurators()
        for ap in all_aps:
            ap_name = ap.get_router_short_name()
            logging.debug('Turning on ap: %s' % ap_name)
            ap.power_up_router()
            bands_info = ap.get_supported_bands()
            for band in bands_info:
                ap.set_band(band['band'])
                ap.apply_settings()
                for pos in range(len(band['channels'])-1):
                    ap.set_channel(pos)
                    ap.apply_settings()
                    ssid = ap_name
                    if len(bands_info) > 1:
                         ssid = ap_name + '_%s' % band['band']
                    ap.set_radio(enabled=True)
                    ap.set_ssid(ssid)
                    ap.set_visibility(visible=True)
                    ap.set_security_disabled()
                    logging.debug('Setting up ap with no security and visible '
                                  'ssid:%s' % ssid)
                    ap.apply_settings()
                    logging.debug('Running client test.')
                    self._run_client_test(ssid)
            logging.debug('Client test complete, powering down router')
            ap.power_down_router()
