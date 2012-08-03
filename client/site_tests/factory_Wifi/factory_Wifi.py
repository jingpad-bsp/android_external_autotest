# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import hashlib
import logging
import os
import re
import time

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import factory
from cros.factory.event_log import EventLog
from cros.factory.test import leds
from autotest_lib.client.cros.rf import agilent_scpi
from autotest_lib.client.cros.rf import lan_scpi
from autotest_lib.client.cros.rf import rf_utils
from autotest_lib.client.cros.rf.config import PluggableConfig


base_config = PluggableConfig({
    'channels': [
        # antenna, channel, freq, fixed_rate, range, level,
        # power_adjustment, min_avg_power, max_avg_power
        #
        # The test will fail if the observed average power is not
        # between min_avg_power and max_avg_power.
        ('1 1',  1, 2412e6, 11,   0, -14, -28, None, None),
        ('2 2',  6, 2437e6, 11,   0, -14, -28, None, None),
        ('1 1',  11, 2462e6, 11,   0, -14, -28, None, None),
        ('2 3',  36, 5180e6,  7, -10, -40, -28, None, None),
        (None, 64, 5320e6,  7, -10, -40, -32, None, None),
        (None, 157, 5785e6,  7, -10, -40, -40, None, None),
        ]
})

delay_secs = 0.5

def run_cmd(command, delay_secs=0, ignore_status=False):
    try:
        ret = utils.system_output(command, ignore_status=ignore_status)
        time.sleep(delay_secs)
        logging.info("Command %s, returned %s" % (command, ret))
        return ret
    except:
        logging.exception("Command Err: %s", command)
        if not ignore_status:
            raise

def get_ath9k_path():
    '''
    Gets the absolute path of ath9k.
    '''
    pattern = "/sys/kernel/debug/ieee80211/phy*/ath9k"
    matches = glob.glob(pattern)
    if len(matches) != 1:
        raise error.TestError('Expected one match for %s but got %s'
                              % (pattern, matches))
    return matches[0]


def get_phy_name(ath9k_path):
    re_phy = re.search(r'ieee80211\/(phy[\d]*)\/ath9k' , ath9k_path)
    if re_phy:
        logging.info('Name of phy[%s]' % re_phy.group(1))
        return re_phy.group(1)
    else:
        raise error.TestError('Expected to find phy name in path[%s]' %
                              ath9k_path)


class factory_Wifi(test.test):
    version = 5

    def run_once(self, n4010a_host, n4010a_port=5025, module_paths=None,
                 config_path=None, interface=None, set_ethernet_ip=None,
                 retries=5):
        assert retries >= 1

        module_names = []

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
                    run_cmd('rmmod %s' % module_name,
                            delay_secs, ignore_status=True)
                # Insert the custom modules
                for module in module_paths:
                    run_cmd('insmod %s' % module, delay_secs)

            # TODO(itspeter): Check services are stopped by ConnectionManager

            if set_ethernet_ip:
                rf_utils.SetEthernetIp(set_ethernet_ip, interface)

            with leds.Blinker(((leds.LED_NUM, 0.25),
                               (leds.LED_CAP, 0.25),
                               (leds.LED_SCR, 0.25),
                               (leds.LED_CAP, 0.25))):
                self._run(n4010a_host, n4010a_port, config_path, retries)
        finally:
            if module_names:
                # Try to remove the custom modules
                run_cmd('rmmod %s' % ' '.join(reversed(module_names)),
                        delay_secs, ignore_status=True)
                # Try to modprobe the default modules back in
                for module_name in module_names:
                    run_cmd('modprobe %s' % module_name,
                            delay_secs, ignore_status=True)

    def _run(self, n4010a_host, n4010a_port, config_path, retries):
        event_log = EventLog.ForAutoTest()
        config = base_config.Read(config_path, event_log=event_log)
        n4010a = agilent_scpi.N4010ASCPI(n4010a_host, n4010a_port, timeout=5)

        logging.info("Tester ID: %s" % n4010a.id)

        power_by_config = {}
        failures = []

        try:
            for channel_info in config['channels']:
                (antenna, channel, freq, fixed_rate, range, level,
                 power_adjustment, min_avg_power, max_avg_power) = channel_info

                for try_number in xrange(retries):
                    logging.info("Try %d for channel %s, antenna %s",
                                 try_number + 1, channel_info, antenna)
                    if antenna is not None:
                        # Assign specific antennai routing.
                        run_cmd("ifconfig wlan0 down", delay_secs)
                        run_cmd("iw phy %s set antenna %s" % (
                                get_phy_name(get_ath9k_path()), antenna))

                    run_cmd("ifconfig wlan0 up")
                    run_cmd("echo 0 > %s/tx99" % get_ath9k_path(),
                            delay_secs, ignore_status=True)
                    # Set up TX99 (continuous transmit) and begin sending.
                    run_cmd("iw wlan0 set channel %d" % channel, delay_secs)
                    run_cmd("echo %d > %s/fixed_rate" % (
                            fixed_rate, get_ath9k_path()), delay_secs)
                    run_cmd("echo 1 > %s/tx99" % get_ath9k_path(),
                            delay_secs)
                    try:
                        power = n4010a.MeasurePower(freq, range=range,
                                                    level=level)
                        power.avg_power -= power_adjustment
                        power.peak_power -= power_adjustment
                        power.tries = try_number + 1
                        if not rf_utils.IsInRange(
                            power.avg_power, min_avg_power, max_avg_power):
                            failures.append('Power for config %s is %s, '
                                            'out of range (%s,%s)'
                                            % ((channel, antenna, fixed_rate),
                                               power.avg_power,
                                               min_avg_power, max_avg_power))
                        break  # Success: Don't retry
                    except lan_scpi.TimeoutError:
                        # Try again
                        logging.info("Timeout on config %s",
                                     (channel, antenna, fixed_rate))
                        n4010a.Reopen()
                        power = None
                else:
                    failures.append("Timeout on config (%s, %s, %s)" %
                                    (channel, antenna, fixed_rate))

                power_by_config[(channel, antenna, fixed_rate)] = power

            if failures:
                raise error.TestError('; '.join(failures))
        finally:
            event_log.Log(
                'wifi_power',
                power_by_config=dict((k, v and v.__dict__)
                                     for k, v in power_by_config.iteritems()))
            logging.info("Power: %s" % power_by_config)
            run_cmd("echo 0 > %s/tx99" % get_ath9k_path(),
                    delay_secs, ignore_status=True)
