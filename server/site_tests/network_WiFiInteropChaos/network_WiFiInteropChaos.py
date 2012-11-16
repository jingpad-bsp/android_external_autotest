# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import pprint
import time

import common

from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest, packet_capture, test
from autotest_lib.server.cros.wlan import connector, disconnector
from autotest_lib.server.cros.wlan import profile_manager
from autotest_lib.server.cros.chaos_config import ChaosAPList


class network_WiFiInteropChaos(test.test):
    version = 1

    def initialize(self, host):
        self.ap_config = ChaosAPList()


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
                    self.capturer.get_capture_file('connect_fail_%s.trc' % bss)
                    raise error.TestFail(e)
                except error.CmdError as e:
                    raise error.TestError(e)
                finally:
                    self.capturer.stop_capture()
                    d.disconnect(ssid)  # To be sure!


    def run_once(self, host, tries=1):
        with packet_capture.PacketCaptureManager() as self.capturer:
            self.capturer.allocate_packet_capture_machine()
            ap_failure = []

            # Loop through AP's and connect to them one by one.
            # Capture all fail to connect test cases and raise
            # one test failure at the end if any AP's fail to connect.
            for ap in self.ap_config:
                ap.power_on()
                try:
                    self.connect_ap(host, ap, tries=tries)
                except error.TestFail as e:
                    model = ap.get_model()
                    brand = ap.get_brand()
                    bss   = ap.get_bss()
                    ap_failure.append({'AP Info': '%s %s' % (brand, model),
                                       'bss'    : '%s'    % bss,
                                       'Error'  : '%s'    % e, })
                ap.power_off()

            if ap_failure:
                raise error.TestFail('Device failed to connect with %d APs: %s'
                                     % (len(ap_failure),
                                     pprint.pformat(ap_failure)))
