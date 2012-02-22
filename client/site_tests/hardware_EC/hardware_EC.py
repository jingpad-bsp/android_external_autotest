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
    def ec_command(self, cmd):
        full_cmd = 'ectool %s' % cmd
        result = utils.system_output(full_cmd)
        logging.info('Command: %s' % full_cmd)
        logging.info('Result: %s' % result)
        return result

    def hello(self):
        response = self.ec_command('hello')
        result = re.search(self.HELLO_RE, response)
        return (result != None)

    def get_fanspeed(self):
        response = self.ec_command('pwmgetfanrpm')
        match = re.search(self.GET_FANSPEED_RE, response).group(1)
        logging.info('Fan speed: %s' % match)
        if match:
            return int(match)
        raise error.TestError('Unable to read fan speed')

    def set_fanspeed(self, rpm):
        response = self.ec_command('pwmsetfanrpm %d' % rpm)
        result = re.search(self.SET_FANSPEED_RE, response)
        logging.info('Set fan speed: %d' % rpm)
        return (result != None)

    def get_temperature(self, idx):
        response = self.ec_command('temps %d' % idx)
        match = re.search(self.TEMP_SENSOR_RE, response).group(1)
        if match:
            return int(match)
        raise error.TestError('Unable to read temperature sensor %d.' % idx)


class hardware_EC(test.test):
    version = 1
    FAN_DELAY = 3
    TEMP_ERR_MSG = 'Abnormal temperature reading on sensor %d.'

    def run_once(self, num_temp_sensor = 1):
        ec = ECControl()

        if not ec.hello():
            raise error.TestError('EC communication failed.')

        # Record the original fan speed and restore it after testing.
        # TODO: Modify this if our EC support auto fan speed control.
        original_rpm = ec.get_fanspeed()

        try:
            ec.set_fanspeed(10000)
            time.sleep(self.FAN_DELAY)
            max_reading = ec.get_fanspeed()
            if max_reading == 0:
                raise error.TestError('Unable to start fan.')

            ec.set_fanspeed(max_reading / 2)
            time.sleep(self.FAN_DELAY)
            current_reading = ec.get_fanspeed()
            if (current_reading < max_reading / 2 or
                current_reading >= max_reading):
                raise error.TestError('Unable to set fan speed.')
        finally:
            ec.set_fanspeed(original_rpm)

        for idx in xrange(0, num_temp_sensor):
            temperature = ec.get_temperature(idx) - 273
            if temperature < 0 or temperature > 100:
                raise error.TestError(TEMP_ERR_MSG % idx);
