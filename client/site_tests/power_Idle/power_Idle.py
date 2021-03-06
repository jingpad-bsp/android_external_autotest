# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.bluetooth import bluetooth_device_xmlrpc_server
from autotest_lib.client.cros.power import power_test
from autotest_lib.client.cros.power import power_utils


class power_Idle(power_test.power_Test):
    """class for power_Idle test.

    Collects power stats when machine is idle

    Current tests,

      | test# | seconds | display   | bluetooth |
      -------------------------------------------
      | 1     | 120     | off       | off       |
      | 2     | 120     | default   | off       |
      | 3     | 120     | default   | on - idle |
      | 4     | 120     | off       | on - idle |

    """
    version = 1

    def initialize(self, pdash_note='', seconds_period=10.):
        super(power_Idle, self).initialize(seconds_period=seconds_period,
                                           pdash_note=pdash_note)

    def run_once(self, warmup_secs=20, idle_secs=120):
        """Collect power stats for idle tests."""

        def measure_it(warmup_secs, idle_secs, tagname):
            time.sleep(warmup_secs)
            tstart = time.time()
            time.sleep(idle_secs)
            self.checkpoint_measurements(tagname, tstart)

        bt_device = bluetooth_device_xmlrpc_server \
            .BluetoothDeviceXmlRpcDelegate()

        with chrome.Chrome():
            # test1 : display off, BT off
            power_utils.set_display_power(power_utils.DISPLAY_POWER_ALL_OFF)
            if not bt_device.set_powered(False):
                raise error.TestFail('Cannot turn off bluetooth adapter.')
            self.start_measurements()
            measure_it(warmup_secs, idle_secs, 'display-off_bluetooth-off')

            # test2 : display default, BT off
            power_utils.set_display_power(power_utils.DISPLAY_POWER_ALL_ON)
            measure_it(warmup_secs, idle_secs,
                       'display-default_bluetooth-off')

            # test3 : display default, BT on
            if not bt_device.set_powered(True):
                logging.warning('Cannot turn on bluetooth adapter.')
                return
            measure_it(warmup_secs, idle_secs, 'display-default_bluetooth-on')

            # test4 : display off, BT on
            power_utils.set_display_power(power_utils.DISPLAY_POWER_ALL_OFF)
            measure_it(warmup_secs, idle_secs, 'display-off_bluetooth-on')

def cleanup(self):
    power_utils.set_display_power(power_utils.DISPLAY_POWER_ALL_ON)
    super(power_Idle, self).cleanup()
