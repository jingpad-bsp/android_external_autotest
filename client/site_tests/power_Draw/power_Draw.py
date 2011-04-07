# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time
from autotest_lib.client.bin import test
from autotest_lib.client.cros import power_status


class power_Draw(test.test):
    version = 1


    def run_once(self, seconds=200, sleep=10):
        status = power_status.get_status()
        if status.linepower[0].online:
            logging.warn('AC power is online -- '
                         'unable to monitor energy consumption')
            return

        start_energy = status.battery[0].energy

        # Let the test run
        for i in range(0, seconds, sleep):
            time.sleep(sleep)
            status.refresh()

        status.refresh()
        end_energy = status.battery[0].energy

        consumed_energy = start_energy - end_energy
        energy_rate = consumed_energy * 60 * 60 / seconds

        keyvals = {}
        keyvals['wh_energy_full'] = status.battery[0].energy_full
        keyvals['wh_start_energy'] = start_energy
        keyvals['wh_end_energy'] = end_energy
        keyvals['wh_consumed_energy'] = consumed_energy
        keyvals['w_average_energy_rate'] = energy_rate
        keyvals['w_end_energy_rate'] = status.battery[0].energy_rate
        keyvals['mc_min_temp'] = status.min_temp
        keyvals['mc_max_temp'] = status.max_temp

        self.write_perf_keyval(keyvals)
