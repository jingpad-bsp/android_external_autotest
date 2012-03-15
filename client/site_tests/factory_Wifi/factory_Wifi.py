# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
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
from autotest_lib.client.cros.rf import rf_utils
from autotest_lib.client.cros.rf.config import PluggableConfig


base_config = PluggableConfig({
    'channels': [
        # channel, freq, fixed_rate, range, level, min_avg_power, max_avg_power
        #
        # The test will fail if the observed average power is not
        # between min_avg_power and max_avg_power.
        (  1, 2412e6, 11,   0, -14,  7.0,  9.0),
        (  6, 2437e6, 11,   0, -14, 10.5, 12.5),
        ( 11, 2462e6, 11,   0, -14,  8.0, 10.0),
        ( 36, 5180e6,  7, -10, -40,  5.0,  7.0),
        ( 64, 5320e6,  7, -10, -40,  7.0,  9.0),
        (157, 5785e6,  7, -10, -40,  3.5,  5.5),
        ]
})

SET_BGSCAN = "/usr/local/lib/flimflam/test/set-bgscan"


class factory_Wifi(test.test):
    version = 1

    def run_once(self, n4010a_host, n4010a_port=5025, module_paths=None,
                 config_path=None, set_interface_ip=None):
        module_names = []

        if set_interface_ip:
            rf_utils.SetInterfaceIp(*set_interface_ip)

        try:
            kernel_release = utils.system_output('uname -r').strip()

            if module_paths:
                module_paths = [
                    path.replace('${kernel_release}', kernel_release)
                    for path in module_paths]

                for path in module_paths:
                    assert os.path.exists(path), path
                    assert path.endswith('.ko'), path
                    # Remove .ko suffix to get the module name
                    module_names.append(os.path.splitext(
                            os.path.basename(path))[0])
                # Remove the current versions of the modules (in reverse, since
                # there may be dependencies)
                for module_name in reversed(module_names):
                    utils.system('rmmod %s' % module_name, ignore_status=True)
                # Insert the custom modules
                for module in module_paths:
                    utils.system('insmod %s' % module)

            # Disable Flimflam background scans, which may interrupt
            # our test.
            utils.system("%s ScanInterval=10000" % SET_BGSCAN,
                         ignore_status=True)

            with leds.Blinker(((leds.LED_NUM, 0.25),
                               (leds.LED_CAP, 0.25),
                               (leds.LED_SCR, 0.25),
                               (leds.LED_CAP, 0.25))):
                self._run(n4010a_host, n4010a_port, config_path)
        finally:
            if module_names:
                # Try to remove the custom modules
                utils.system('rmmod %s' % ' '.join(reversed(module_names)),
                             ignore_status=True)
                # Try to modprobe the default modules back in
                for module_name in module_names:
                    utils.system('modprobe %s' % module_name,
                                 ignore_status=True)
            utils.system("%s ScanInterval=180" % SET_BGSCAN,
                         ignore_status=True)

    def _run(self, n4010a_host, n4010a_port, config_path):
        config = base_config.Read(config_path)
        n4010a = agilent_scpi.N4010ASCPI(n4010a_host, n4010a_port, timeout=5)

        logging.info("Tester ID: %s" % n4010a.id)

        power_by_channel = {}
        failures = []

        try:
            pattern = "/sys/kernel/debug/ieee80211/phy*/ath9k"
            matches = glob.glob(pattern)
            if len(matches) != 1:
                raise error.TestError('Expected one match for %s but got %s'
                                      % (pattern, matches))
            ath9k = matches[0]
            for channel_info in config['channels']:
                (channel, freq, fixed_rate, range, level,
                 min_avg_power, max_avg_power) = channel_info

                utils.system("echo 0 > %s/tx99" % ath9k,
                             ignore_status=True)
                # Set up TX99 (continuous transmit) and begin sending.
                utils.system("iw wlan0 set channel %d" % channel)
                utils.system("echo %d > %s/fixed_rate" % (fixed_rate, ath9k))
                utils.system("echo 1 > %s/tx99" % ath9k)
                try:
                    power = n4010a.MeasurePower(freq, range=range, level=level)
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
