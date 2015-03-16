# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import re
import logging

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error


def has_ectool():
    """Determine if ectool shell command is present.

    Returns:
        boolean true if avail, false otherwise.
    """
    cmd = 'which ectool'
    return (utils.system(cmd, ignore_status=True) == 0)

class EC(object):
    """Class for CrOS embedded controller (EC)."""
    HELLO_RE = "EC says hello"
    GET_FANSPEED_RE = "Current fan RPM: ([0-9]*)"
    SET_FANSPEED_RE = "Fan target RPM set."
    TEMP_SENSOR_RE = "Reading temperature...([0-9]*)"
    TOGGLE_AUTO_FAN_RE = "Automatic fan control is now on"
    # For battery, check we can see a non-zero capacity value.
    BATTERY_RE = "Design capacity:\s+[1-9]\d*\s+mAh"
    LIGHTBAR_RE = "^ 05\s+3f\s+3f$"


    def __init__(self):
        """Constructor."""
        if not has_ectool():
            ec_info = utils.system_output("mosys ec info",
                                          ignore_status=True)
            logging.warning("Ectool absent on this platform ( %s )",
                         ec_info)
            raise error.TestNAError("Platform doesn't support ectool")

    def ec_command(self, cmd):
        """Executes ec command and returns results.

        @param cmd: string of command to execute.

        @returns: string of results from ec command.
        """
        full_cmd = 'ectool %s' % cmd
        result = utils.system_output(full_cmd)
        logging.info('Command: %s', full_cmd)
        logging.info('Result: %s', result)
        return result

    def hello(self):
        """Test EC hello command.

        @returns True if success False otherwise.
        """
        response = self.ec_command('hello')
        return (re.search(self.HELLO_RE, response) is not None)

    def auto_fan_ctrl(self):
        """Turns auto fan ctrl on.

        @returns True if success False otherwise.
        """
        response = self.ec_command('autofanctrl')
        logging.info('Turned on auto fan control.')
        return (re.search(self.TOGGLE_AUTO_FAN_RE, response) is not None)

    def get_fanspeed(self):
        """Gets fanspeed.

        @raises error.TestError if regexp fails to match.

        @returns integer of fan speed RPM.
        """
        response = self.ec_command('pwmgetfanrpm')
        match = re.search(self.GET_FANSPEED_RE, response)
        if not match:
            raise error.TestError('Unable to read fan speed')

        rpm = int(match.group(1))
        logging.info('Fan speed: %d', rpm)
        return rpm

    def set_fanspeed(self, rpm):
        """Sets fan speed.

        @params rpm: integer of fan speed RPM to set

        @returns True if success False otherwise.
        """
        response = self.ec_command('pwmsetfanrpm %d' % rpm)
        logging.info('Set fan speed: %d', rpm)
        return (re.search(self.SET_FANSPEED_RE, response) is not None)

    def get_temperature(self, idx):
        """Gets temperature from idx sensor.

        @params idx: integer of temp sensor to read.

        @raises error.TestError if fails to read sensor.

        @returns integer of temperature reading in degrees Kelvin.
        """
        response = self.ec_command('temps %d' % idx)
        match = re.search(self.TEMP_SENSOR_RE, response)
        if not match:
            raise error.TestError('Unable to read temperature sensor %d' % idx)

        return int(match.group(1))

    def get_battery(self):
        """Get battery presence (design capacity found).

        @returns True if success False otherwise.
        """
        response = self.ec_command('battery')
        return (re.search(self.BATTERY_RE, response) is not None)

    def get_lightbar(self):
        """Test lightbar.

        @returns True if success False otherwise.
        """
        self.ec_command('lightbar on')
        self.ec_command('lightbar init')
        self.ec_command('lightbar 4 255 255 255')
        response = self.ec_command('lightbar')
        self.ec_command('lightbar off')
        return (re.search(self.LIGHTBAR_RE, response, re.MULTILINE) is not None)
