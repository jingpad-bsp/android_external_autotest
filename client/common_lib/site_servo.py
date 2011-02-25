# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import xmlrpclib
from autotest_lib.client.common_lib import error


class Servo(object):
    """
    Conduit to servo board connected to DUT
    """

    def initialize(self, servo_host='', servo_port='', verbose=False):
        """
        servo_host: name or IP address of server servod is running on
        servo_port: TCP port on which servod is listening on for this DUT
        """
        self._remote = ''.join(['http://', servo_host, ':', servo_port])
        self._server = xmlrpclib.ServerProxy(self._remote, verbose=verbose)
        # Try connecting to the server
        self._server.system.listMethods()


    def get_gpio(self, gpio_name=''):
        """
        gpio_name:  name of GPIO pin
        """
        if not gpio_name:
            raise error.TestFail('get_gpio: gpio_name not specified')

        value = self._server.get_gpio(gpio_name)
        return value


    def set_gpio(self, gpio_name='', gpio_value=''):
        """
        gpio_name:  name of GPIO pin
        gpio_value: value to set GPIO pin to
        """
        if not gpio_name or not gpio_value:
            raise error.TestFail('set_gpio: gpio_name or value not specified')

        status = self._server.set_gpio(gpio_name, gpio_value)
        return status
