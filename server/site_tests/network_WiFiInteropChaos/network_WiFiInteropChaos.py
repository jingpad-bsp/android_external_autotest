# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Chaos lab static connection test."""

import logging
import os

import common

from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest, test
from autotest_lib.server.cros.wlan import connector, disconnector
from autotest_lib.server.cros.wlan import profile_manager


class network_WiFiInteropChaos(test.test):
    """Test to connect to statically configured APs in the Chaos lab."""
    version = 1


    def initialize(self, host):
        # Install client autotest dirs into /usr/local/autotest
        # on the DUT.
        client_at = autotest.Autotest(host)
        client_at.install()


    def connect_ap(self, host, ap, tries=1):
        """Establishes a connetion to the ap.

        Params:
            @param host: Autotest host instance.
            @param ap: ChaosAP instance defined in cros.chaos_config.
            @param tries: number of times to try to connect to the ap.
        """

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
                connection_success = True
                try:
                    self.capturer.start_capture(frequency, bandwidth)
                    logging.info('Connecting to %s.  Attempt %d', ssid, i+1)
                    c.connect(ssid, security=security, psk=psk)
                    pm.clear_global_profile()
                except (connector.ConnectException,
                        connector.ConnectFailed,
                        connector.ConnectTimeout) as e:
                    logging.info('Failed to connect to %s.', ssid)
                    connection_success = False
                except error.CmdError as e:
                    raise error.TestError(e)
                finally:
                    self.capturer.stop_capture()
                    file_name = 'success' if connection_success else 'fail'
                    capture_file = os.path.join(self.outputdir,
                                                'connect_%s_%s_try_%d.trc' %
                                                (file_name, bss, i+1))
                    self.capturer.get_capture_file(capture_file)
                    d.disconnect(ssid)  # To be sure!
                    if not connection_success:
                        msg = ('DUT failed to connect to "%s %s" on try %d. '
                               'Reason: %s' % (ap.get_brand(), ap.get_model(),
                                               i+1, str(e)))
                        raise error.TestFail(msg)


    def run_once(self, host, capturer=None, ap=None, tries=1):
        """
        This test connects to an ap 'tries' number of times.

        Params:
            @param host: Autotest host instance.
            @param capturer: packet_capture instance defined in packet_capture.
            @param ap: ChaosAP instance defined in cros.chaos_config.
            @param tries: number of times to try to connect to the ap.
        """
        logging.info(ap)
        self.capturer = capturer

        mac_addresses = host.run('ip link show').stdout
        logging.info('Device MAC addresses\n %s',  mac_addresses)

        # Loop through AP's and connect to them one by one.
        # Capture all fail to connect test cases and raise
        ap.power_on()
        try:
            self.connect_ap(host, ap, tries=tries)
        finally:
            ap.power_off()
