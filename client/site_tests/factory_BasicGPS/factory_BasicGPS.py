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
ENABLE_GPS = 'AT$NWGPS=1'
# This commands start tracking mode, and run for a while.
START_GPS_TRACKING = 'AT$NWGPSSTART=3,1,64000,1,100,250'

class factory_BasicGPS(test.test):
    version = 1

    def run_once(self, retry, dev_modem='/dev/ttyUSB0', dev_gps='/dev/ttyUSB3'):
        '''Gets raw NMEA data from GPS to ensure the connectivity.

        @param dev_modem: Path to modem.
        @param dev_gps: Path to extract GPS data.
        @param retry: A number indicates times to retry because some GPS
                      module have its own format, NMEA format might not come
                      as its first response.
        '''
        def read_response(serial):
            '''Reads response from the modem until a timeout.'''
            line = serial.readline()
            factory.log('modem[ %r' % line)
            return line.rstrip('\r\n')

        def send_command(serial, command):
            '''Sends a command to the modem and discards the echo.'''
            serial.write(command + '\r')
            factory.log('modem] %r' % command)
            echo = read_response(serial)

        def check_response(serial, expected_re):
            '''Reads response and checks with a regular expression.'''
            response = read_response(serial)
            if not re.match(expected_re, response):
                raise error.TestError(
                    'Expected %r but got %r' % (expected_re, response))

        def check_valid_nmea(data):
            '''Checks whether the data is valid NMEA format.'''
            match = re.match(r'\$(.*)\*(\w\w)', data)
            if match:
                # Examine the checksum.
                checksum = 0
                for char in match.group(1):
                    checksum ^= ord(char)
                if int(match.group(2), 16) == checksum:
                    return True
            return False

        try:
            # Kill off modem manager, which might be holding the device open.
            utils.system("stop modemmanager", ignore_status=True)

            serial_modem = pyserial.Serial(dev_modem, timeout=2)
            serial_modem.read(serial_modem.inWaiting())  # Empty the buffer.
            serial_gps = pyserial.Serial(dev_gps, timeout=2)
            serial_gps.read(serial_gps.inWaiting())  # Empty the buffer.

            # Send an AT command and expect 'OK'
            send_command(serial_modem, 'AT')
            check_response(serial_modem, DEVICE_NORMAL_RESPONSE)

            # Enable GPS.
            send_command(serial_modem, ENABLE_GPS)
            send_command(serial_modem, START_GPS_TRACKING)

            # See if we can get valid NMEA data.
            while retry > 0:
                response = read_response(serial_gps)
                if check_valid_nmea(response):
                    return
                retry -= 1

            raise error.TestError('No valid NMEA data found')

        finally:
            try:
                # Restart the modem manager.
                utils.system("start modemmanager", ignore_status=True)
            except Exception as e:
                factory.log('Exception - %s' % e)
