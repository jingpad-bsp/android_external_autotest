# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import servo


class power_Servo(test.test):
    version = 1

    def run_once(self, servo_host='', servo_port='', action='', **kwargs):
        if servo_host is None or servo_port is None:
            raise error.TestFail('servo_host or servo_port not specified')

        try:
            self.servo = servo.Servo()
            self.servo.initialize(servo_host=servo_host,
                                  servo_port=servo_port)
        except:
            raise error.TestFail('Could not connect to servod')

        if action == 'get_gpio':
            self._get_gpio(*kwargs)
        elif action == 'set_gpio':
            self._set_gpio(*kwargs)
        else:
            raise error.TestFail('Unsupported action: %s', action)


    def _get_gpio(self, gpio_name='', gpio_expected_value=''):
        value = self.servo.get_gpio(gpio_name=gpio_name)
        if gpio_expected_value and str(value) != gpio_expected_value:
            raise error.TestFail('gpio value did not match expected value')


    def _set_gpio(self, gpio_name='', gpio_value=''):
        self.servo.set_gpio(gpio_name=gpio_name, gpio_value=gpio_value)
