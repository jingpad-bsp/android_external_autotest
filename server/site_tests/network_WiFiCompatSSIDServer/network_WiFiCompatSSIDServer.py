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
from autotest_lib.server.cros.chaos_ap_configurators \
import ap_configurator_factory
from autotest_lib.server.cros.chaos_ap_configurators \
import download_chromium_prebuilt


class network_WiFiCompatSSIDServer(test.test):
    version = 1

    def _configure_router_ssid_settings(self, ap, ssid, visible):
        ap.set_radio(enabled=True)
        ap.set_security_disabled()
        ap.set_ssid(ssid)
        ap.set_visibility(visible=visible)
        ap.apply_settings()

    def _run_client_test(self, ssid, visible):
        client_at = autotest.Autotest(self.client)
        self.job.set_state('client_passed', None)
        client_at.run_test(self.client_test, ssid=ssid, ssid_visible=visible)
        state = self.job.get_state('client_passed')
        if state is None:
            raise error.TestFail('The client test did not return a state value.'
                                 ' Perhaps it did not run.')
        elif state is False:
            raise error.TestFail('The client test to connect to a network with '
                                 'ssid visibility set to %s failed.  See the '
                                 'client test logs for more information.' %
                                 visible)

    def run_once(self, host=None):
        self.client = host
        self.client_test = 'network_WiFiCompatSSID'

        if download_chromium_prebuilt.download_chromium_prebuilt_binaries():
            raise error.TestError('The binaries were just downloaded.  Please '
                                  'run: (outside-chroot) <path to chroot tmp '
                                  'directory>/ %s./ chromedriver'
                                  % download_chromium_prebuilt.DOWNLOAD_PATH)

        config_file = os.path.join(self.job.configdir, 'wifi_compat_config')
        factory = ap_configurator_factory.APConfiguratorFactory(config_file)
        factory.turn_off_all_routers()
        ap = factory.get_ap_configurator_by_short_name('WRT54G2')

        ssid = 'ssid-test-1'
        visible = True
        self._configure_router_ssid_settings(ap, ssid, visible)
        logging.info('WifiCompatSSID: start client test visible connect test')
        self._run_client_test(ssid, visible)

        visible = False
        self._configure_router_ssid_settings(ap, ssid, visible)
        logging.info('WifiCompatSSID: start client test invisible connect test')
        self._run_client_test(ssid, visible)
