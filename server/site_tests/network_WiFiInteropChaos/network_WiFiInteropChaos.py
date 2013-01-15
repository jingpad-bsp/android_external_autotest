# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

import common

from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest, test
from autotest_lib.server.cros.wlan import connector, disconnector
from autotest_lib.server.cros.wlan import profile_manager


class network_WiFiInteropChaos(test.test):
    version = 1


    def initialize(self, host):
        # Install client autotest dirs into /usr/local/autotest
        # on the DUT.
        client_at = autotest.Autotest(host)
        client_at.install()


    def connect_ap(self, host, ap, tries=1):
        c = connector.Connector(host)
        d = disconnector.Disconnector(host)

        frequency = ap.get_frequency()
        bss = ap.get_bss()
        bandwidth = ap.get_bandwidth()
        psk = ap.get_psk()
        security = ap.get_security()
        ssid = ap.get_ssid()

        d.disconnect(ssid)  # To be sure!
        with profile_manager.ProfileManager(host) as pm:
            for i in xrange(tries):
                try:
                    self.capturer.start_capture(frequency, bandwidth)
                    logging.info('Connecting to %s.  Attempt %d', ssid, i)
                    c.connect(ssid, security=security, psk=psk)
                    pm.clear_global_profile()
                except (connector.ConnectException,
                        connector.ConnectFailed,
                        connector.ConnectTimeout) as e:
                    logging.info('Failed to connect to %s.', ssid)
                    self.capturer.stop_capture()
                    capture_file = os.path.join(self.outputdir,
                                                'connect_fail_%s.trc' % bss)
                    self.capturer.get_capture_file(capture_file)
                    msg = ('DUT failed to connect to "%s %s" on attempt %d. '
                           'Reason: %s' % (ap.get_brand(), ap.get_model(), i+1,
                                           str(e)))
                    raise error.TestFail(msg)
                except error.CmdError as e:
                    raise error.TestError(e)
                finally:
                    self.capturer.stop_capture()
                    d.disconnect(ssid)  # To be sure!


    def run_once(self, host, capturer=None, ap=None, tries=1):
        """
        This test connects to an ap 'tries' number of times.

        Params:
            host: Autotest host instance.
            capturer: packet_capture instance defined in packet_capture.
            ap: ChaosAP instance defined in cros.chaos_config
        """
        logging.info(ap)
        self.capturer = capturer

        # Loop through AP's and connect to them one by one.
        # Capture all fail to connect test cases and raise
        ap.power_on()
        try:
            self.connect_ap(host, ap, tries=tries)
        finally:
            ap.power_off()
