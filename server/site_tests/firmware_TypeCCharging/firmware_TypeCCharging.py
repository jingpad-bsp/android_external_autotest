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


    def run_once(self, host, args_dict):
        """Compares VBUS voltage with charging setting.

        When charging voltage == 0, Plankton will act as a power sink and draws
        5 volts from DUT. Other charging voltage should be seen on USB type C
        VBUS INA meter in a 12% range.

        @raise TestFail: If VBUS voltage is not in range.
        """
        self._host = host
        self._plankton = plankton.Plankton(args_dict)

        for charging_voltage in self._plankton.get_charging_voltages():
            self._plankton.charge(charging_voltage)
            expected_vbus_voltage = float(
                    charging_voltage if charging_voltage > 0 else
                    self.USBC_SINK_VOLTAGE)
            tolerance = self.VBUS_TOLERANCE * expected_vbus_voltage
            vbus_voltage = self._plankton.vbus_voltage
            vbus_current = self._plankton.vbus_current
            logging.info('Charging %dV: VBUS V=%f I=%f', charging_voltage,
                         vbus_voltage, vbus_current)

            if math.fabs(expected_vbus_voltage - vbus_voltage) > tolerance:
                raise error.TestFail(
                        'VBUS voltage out of range: %f (%f, delta %f)' %
                        (vbus_voltage, expected_vbus_voltage, tolerance))

            if charging_voltage == 0 and vbus_current > 0:
                raise error.TestFail('Failed to consume power from DUT')
