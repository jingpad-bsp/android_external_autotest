# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import serial as pyserial

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory


# Modem commands.
DEVICE_NORMAL_RESPONSE = 'OK'


class factory_BasicCellular(test.test):
    version = 1

    def run_once(self, imei_re, iccid_re, dev='/dev/ttyUSB0'):
        '''Connects to the modem, checking the IMEI and ICCID.

        @param imei_re: The regular expression of expected IMEI.
        @param iccid_re: The regular expression of expected ICCID.
        @param dev: Path to the modem. Default to /dev/ttyUSB0.
        '''
        def read_response():
            '''Reads response from the modem until a timeout.'''
            line = serial.readline()
            factory.log('modem[ %r' % line)
            return line.rstrip('\r\n')

        def send_command(command):
            '''Sends a command to the modem and discards the echo.'''
            serial.write(command + '\r')
            factory.log('modem] %r' % command)
            echo = read_response()

        def check_response(expected_re):
            '''Reads response and checks with a regular expression.'''
            response = read_response()
            if not re.match(expected_re, response):
                raise error.TestError(
                    'Expected %r but got %r' % (expected_re, response))

        try:
            # Kill off modem manager, which might be holding the device open.
            utils.system("stop modemmanager", ignore_status=True)

            serial = pyserial.Serial(dev, timeout=2)

            # Send an AT command and expect 'OK'
            send_command('AT')
            check_response(DEVICE_NORMAL_RESPONSE)

            # Check IMEI.
            send_command('AT+CGSN')
            check_response(imei_re)
            check_response('')
            check_response(DEVICE_NORMAL_RESPONSE)

            # Check ICCID.
            send_command('AT+ICCID')
            check_response(iccid_re)
            check_response('')
            check_response(DEVICE_NORMAL_RESPONSE)
        finally:
            try:
                # Restart the modem manager.
                utils.system("start modemmanager", ignore_status=True)
            except Exception as e:
                factory.log('Exception - %s' % e)
