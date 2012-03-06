# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import logging
import os
import time

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import leds
from autotest_lib.client.cros.rf import agilent_scpi
from autotest_lib.client.cros.rf import lan_scpi
from autotest_lib.client.cros.rf.config import PluggableConfig


base_config = PluggableConfig({
    'channels': [
        # channel, freq, fixed_rate, min_avg_power, max_avg_power
        #
        # The test will fail if the observed average power is not
        # between min_avg_power and max_avg_power.
        (  1, 2412e6, 11,  7.0,  9.0),
        (  6, 2437e6, 11, 10.5, 12.5),
        ( 11, 2462e6, 11,  8.0, 10.0),
        ( 36, 5180e6,  7,  5.0,  7.0),
        ( 64, 5320e6,  7,  7.0,  9.0),
        (157, 5785e6,  7,  3.5,  5.5),
        ]
})


class factory_Wifi(test.test):
    version = 1

    def run_once(self, n4010a_host, config_path=None):
        with leds.Blinker(((leds.LED_NUM, 0.25),
                           (leds.LED_CAP, 0.25),
                           (leds.LED_SCR, 0.25),
                           (leds.LED_CAP, 0.25))):
            self._run(n4010a_host, config_path)

    def _run(self, n4010a_host, config_path):
        config = base_config.Read(config_path)
        n4010a = agilent_scpi.N4010ASCPI(n4010a_host, timeout=5)

        logging.info("Tester ID: %s" % n4010a.id)

        set_bgscan = "/usr/local/lib/flimflam/test/set-bgscan"
        # Disable Flimflam background scans, which may interrupt
        # our test.
        utils.system("%s ScanInterval=10000" % set_bgscan)

        power_by_channel = {}
        failures = []

        try:
            ath9k = "/sys/kernel/debug/ieee80211/phy0/ath9k"
            for channel_info in config['channels']:
                (channel, freq, fixed_rate,
                 min_avg_power, max_avg_power) = channel_info

                utils.system("echo 0 > %s/tx99" % ath9k,
                             ignore_status=True)
                # Set up TX99 (continuous transmit) and begin sending.
                utils.system("iw wlan0 set channel %d" % channel)
                utils.system("echo %d > %s/fixed_rate" % (fixed_rate, ath9k))
                utils.system("echo 1 > %s/tx99" % ath9k)
                try:
                    power = n4010a.MeasurePower(freq)
                    if (power.avg_power < min_avg_power or
                        power.avg_power > max_avg_power):
                        failures.append(
                            'Power for channel %d is %g, out of range (%g,%g)' %
                            (channel, power.avg_power,
                             min_avg_power, max_avg_power))
                except lan_scpi.TimeoutError:
                    failures.append("Timeout on channel %d" % channel)
                    n4010a.Reopen()
                    power = None
                power_by_channel[channel] = power

            if failures:
                raise error.TestError('; '.join(failures))
        finally:
            logging.info("Power: %s" % [
                    (k, power_by_channel[k])
                    for k in sorted(power_by_channel.keys())])
            utils.system("echo 0 > %s/tx99" % ath9k,
                         ignore_status=True)
            utils.system("%s ScanInterval=180" % set_bgscan,
                         ignore_status=True)
