# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This is a hardware test for EC. The test uses ectool to check if the EC can
# receive message from host and send expected reponse back to host. It also
# checks basic EC functionality, such as FAN and temperature sensor.


import re
import time
import logging

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class ECControl(object):
    HELLO_RE = "EC says hello"
    GET_FANSPEED_RE = "Current fan RPM: ([0-9]*)"
    SET_FANSPEED_RE = "Fan target RPM set."
    TEMP_SENSOR_RE = "Reading temperature...([0-9]*)"
    TOGGLE_AUTO_FAN_RE = "Automatic fan control is now on"
    # For battery, check we can see a non-zero capacity value.
    BATTERY_RE = "Design capacity:\s+[1-9]\d*\s+mAh"
    LIGHTBAR_RE = "^ 05\s+3f\s+3f$"

    def ec_command(self, cmd):
        full_cmd = 'ectool %s' % cmd
        result = utils.system_output(full_cmd)
        logging.info('Command: %s' % full_cmd)
        logging.info('Result: %s' % result)
        return result

    def hello(self):
        response = self.ec_command('hello')
        return (re.search(self.HELLO_RE, response) is not None)

    def auto_fan_ctrl(self):
        response = self.ec_command('autofanctrl')
        logging.info('Turned on auto fan control.')
        return (re.search(self.TOGGLE_AUTO_FAN_RE, response) is not None)

    def get_fanspeed(self):
        response = self.ec_command('pwmgetfanrpm')
        match = re.search(self.GET_FANSPEED_RE, response)
        if not match:
            raise error.TestError('Unable to read fan speed')

        rpm = int(match.group(1))
        logging.info('Fan speed: %d', rpm)
        return rpm

    def set_fanspeed(self, rpm):
        response = self.ec_command('pwmsetfanrpm %d' % rpm)
        logging.info('Set fan speed: %d', rpm)
        return (re.search(self.SET_FANSPEED_RE, response) is not None)

    def get_temperature(self, idx):
        response = self.ec_command('temps %d' % idx)
        match = re.search(self.TEMP_SENSOR_RE, response)
        if not match:
            raise error.TestError('Unable to read temperature sensor %d' % idx)

        return int(match.group(1))

    def get_battery(self):
        response = self.ec_command('battery')
        return (re.search(self.BATTERY_RE, response) is not None)

    def get_lightbar(self):
        self.ec_command('lightbar on')
        self.ec_command('lightbar init')
        self.ec_command('lightbar 4 255 255 255')
        response = self.ec_command('lightbar')
        self.ec_command('lightbar off')
        return (re.search(self.LIGHTBAR_RE, response, re.MULTILINE) is not None)


class hardware_EC(test.test):
    version = 1

    def run_once(self,
                 num_temp_sensor=0,
                 temp_sensor_to_test=None,
                 test_fan=False,
                 fan_rpm_error_margin=200,
                 test_battery=False,
                 test_lightbar=False,
                 fan_delay_secs=3):
        ec = ECControl()

        if not ec.hello():
            raise error.TestError('EC communication failed')

        if test_fan:
            try:
                ec.set_fanspeed(10000)
                time.sleep(fan_delay_secs)
                max_reading = ec.get_fanspeed()
                if max_reading == 0:
                    raise error.TestError('Unable to start fan')

                target_fanspeed = max_reading / 2
                ec.set_fanspeed(target_fanspeed)
                time.sleep(fan_delay_secs)
                current_reading = ec.get_fanspeed()

                # Sometimes the actual fan speed is close but not equal to
                # the target speed, so we add some error margin here.
                lower_bound = target_fanspeed - fan_rpm_error_margin
                upper_bound = target_fanspeed + fan_rpm_error_margin
                if not (lower_bound <= current_reading <= upper_bound):
                    raise error.TestError('Unable to set fan speed')
            finally:
                ec.auto_fan_ctrl()

        if temp_sensor_to_test is None:
            temp_sensor_to_test = list(range(num_temp_sensor))

        for idx in temp_sensor_to_test:
            temperature = ec.get_temperature(idx) - 273
            if temperature < 0 or temperature > 100:
                raise error.TestError(
                        'Abnormal temperature reading on sensor %d' % idx);

        if test_battery and not ec.get_battery():
            raise error.TestError('Battery communication failed')

        if test_lightbar and not ec.get_lightbar():
            raise error.TestError('Lightbar communication failed')
