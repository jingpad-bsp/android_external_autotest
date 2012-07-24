# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faftsequence import FAFTSequence

class firmware_ECBattery(FAFTSequence):
    """
    Servo based EC thermal battery status report test.
    """
    version = 1

    # Battery status path in sysfs
    BATTERY_STATUS = '/sys/class/power_supply/BAT0/status'

    # Battery voltage reading path in sysfs
    BATTERY_VOLTAGE_READING = '/sys/class/power_supply/BAT0/voltage_now'

    # Battery current reading path in sysfs
    BATTERY_CURRENT_READING = '/sys/class/power_supply/BAT0/current_now'

    # Maximum allowed error of voltage reading in mV
    VOLTAGE_MV_ERROR_MARGIN = 300

    # Maximum allowed error of current reading in mA
    CURRENT_MA_ERROR_MARGIN = 300

    # Maximum allowed battery temperature in C
    BATTERY_TEMP_UPPER_BOUND = 70

    # Minimum allowed battery temperature in C
    BATTERY_TEMP_LOWER_BOUND = 0


    def _check_voltage_match(self):
        """Check if voltage reading from kernel and servo match.

        Raises:
          error.TestFail: Raised when the two reading mismatch by more than
            VOLTAGE_MV_ERROR_MARGIN mV.
        """
        servo_reading = int(self.servo.get('ppvar_vbat_mv'))
        # Kernel gives voltage value in uV. Convert to mV here.
        kernel_reading = int(self.faft_client.run_shell_command_get_output(
                'cat %s' % self.BATTERY_VOLTAGE_READING)[0]) / 1000
        if abs(servo_reading - kernel_reading) > self.VOLTAGE_MV_ERROR_MARGIN:
            raise error.TestFail(
                    "Voltage reading from servo and kernel mismatch.")


    def _check_current_match(self):
        """Check if current reading from kernel and servo match.

        Raises:
          error.TestFail: Raised when the two reading mismatch by more than
            CURRENT_MA_ERROR_MARGIN mA.
        """
        servo_reading = int(self.servo.get('ppvar_vbat_ma'))
        # Kernel gives current value in uA. Convert to mA here.
        kernel_reading = int(self.faft_client.run_shell_command_get_output(
                'cat %s' % self.BATTERY_CURRENT_READING)[0]) / 1000
        status = self.faft_client.run_shell_command_get_output(
                'cat %s' % self.BATTERY_STATUS)[0]

        # If battery is not discharging, servo gives negative value.
        if status != "Discharging":
            servo_reading = -servo_reading
        if abs(servo_reading - kernel_reading) > self.CURRENT_MA_ERROR_MARGIN:
            raise error.TestFail(
                    "Current reading from servo and kernel mismatch.")


    def _check_temperature(self):
        """Check if battery temperature is reasonable.

        Raises:
          error.TestFail: Raised when battery tempearture is higher than
            BATTERY_TEMP_UPPER_BOUND or lower than BATTERY_TEMP_LOWER_BOUND.
        """
        battery_temp = float(self.send_uart_command_get_output("battery",
                ["Temp:.+\(([0-9\.]+) C\)"])[0].group(1))
        logging.info("Battery temperature is %f C" % battery_temp)
        if (battery_temp > self.BATTERY_TEMP_UPPER_BOUND or
            battery_temp < self.BATTERY_TEMP_LOWER_BOUND):
            raise error.TestFail("Abnormal battery temperature.")


    def run_once(self, host=None):
        if not self.check_ec_capability(['battery']):
            return
        logging.info("Checking battery current reading...")
        self._check_current_match()

        logging.info("Checking battery voltage reading...")
        self._check_voltage_match()

        logging.info("Checking battery temperature...")
        self._check_temperature()
