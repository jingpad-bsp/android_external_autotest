# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import site_power_status


class system_PowerDraw(test.test):
    version = 1


    def run_once(self, seconds=200):
        status = site_power_status.get_status()
        if status.linepower[0].online:
            logging.warn('AC power is online -- '
                         'unable to monitor energy consumption')
            return

        start_energy = status.battery[0].energy

        # Let the test run
        time.sleep(seconds)

        status.refresh()
        end_energy = status.battery[0].energy

        keyvals = {}
        keyvals['wh_energy_full'] = status.battery[0].energy_full
        keyvals['wh_start_energy'] = start_energy
        keyvals['wh_end_energy'] = end_energy
        keyvals['wh_consumed_energy'] = start_energy - end_energy
        self.write_perf_keyval(keyvals)
