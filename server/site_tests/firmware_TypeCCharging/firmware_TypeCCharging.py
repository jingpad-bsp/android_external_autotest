# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a USB type C charging test using Plankton board."""

import logging
import math

from autotest_lib.client.common_lib import error
from autotest_lib.server import test
from autotest_lib.server.cros.servo import plankton

class firmware_TypeCCharging(test.test):
    """USB type C charging test."""
    version = 1

    USBC_SINK_VOLTAGE = 5
    VBUS_TOLERANCE = 0.12
    VBUS_5V_CURRENT_RANGE = (2, 3.4)


    def run_once(self, host, args_dict):
        """Compares VBUS voltage and current with charging setting.

        When charging voltage == 0, Plankton will act as a power sink and draws
        5 volts from DUT. Other charging voltage should be seen on USB type C
        VBUS INA meter in a 12% range.

        When charging voltage == 5, Plankton INA current should be seen around
        3 Amps (we set the range among 2 ~ 3.4 Amps just as in factory testing).
        Other positive charging votage should not be less than 0 Amp.

        @raise TestFail: If VBUS voltage or current is not in range.
        """
        plankton_host = plankton.Plankton(args_dict)

        for charging_voltage in plankton_host.get_charging_voltages():
            plankton_host.charge(charging_voltage)
            plankton_host.poll_pd_state(
                    'source' if charging_voltage > 0 else 'sink')
            expected_vbus_voltage = float(
                    charging_voltage if charging_voltage > 0 else
                    self.USBC_SINK_VOLTAGE)
            tolerance = self.VBUS_TOLERANCE * expected_vbus_voltage
            vbus_voltage = plankton_host.vbus_voltage
            vbus_current = plankton_host.vbus_current
            logging.info('Charging %dV: VBUS V=%f I=%f', charging_voltage,
                         vbus_voltage, vbus_current)

            if math.fabs(expected_vbus_voltage - vbus_voltage) > tolerance:
                raise error.TestFail(
                        'VBUS voltage out of range: %f (%f, delta %f)' %
                        (vbus_voltage, expected_vbus_voltage, tolerance))

            if charging_voltage == 0 and vbus_current > 0:
                raise error.TestFail('Failed to consume power from DUT')

            if charging_voltage > 0 and vbus_current <= 0:
                raise error.Testfail(
                        'VBUS current less than 0 in %d volt: %f' %
                        (charging_voltage, vbus_current))

            if (charging_voltage == 5 and
                (vbus_current < self.VBUS_5V_CURRENT_RANGE[0] or
                 vbus_current > self.VBUS_5V_CURRENT_RANGE[1])):
                raise error.TestFail(
                        'VBUS current out of range in 5 volt: %f %r' %
                        (vbus_current, self.VBUS_5V_CURRENT_RANGE))
