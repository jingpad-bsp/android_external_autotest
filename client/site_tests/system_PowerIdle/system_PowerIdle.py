# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, site_power_status


class system_PowerIdle(test.test):
    version = 1

    def initialize(self):
        self.status = site_power_status.get_status()

        if self.status.linepower[0].online:
            raise error.TestNAError(
                  'This test needs to be run with the AC power offline')
        

    def warmup(self, warmup_time=60):
        time.sleep(warmup_time)


    def run_once(self, idle_time=120):
        time.sleep(idle_time)
        self.status.refresh()


    def postprocess_iteration(self):
        keyvals = {}
        keyvals['ah_charge_full'] = self.status.battery[0].charge_full
        keyvals['ah_charge_full_design'] = \
                                self.status.battery[0].charge_full_design
        keyvals['ah_charge_now'] = self.status.battery[0].charge_now
        keyvals['a_current_now'] = self.status.battery[0].current_now
        keyvals['wh_energy'] = self.status.battery[0].energy
        keyvals['w_energy_rate'] = self.status.battery[0].energy_rate
        keyvals['h_remaining_time'] = self.status.battery[0].remaining_time
        keyvals['v_voltage_min_design'] = \
                                self.status.battery[0].voltage_min_design
        keyvals['v_voltage_now'] = self.status.battery[0].voltage_now

        self.write_perf_keyval(keyvals)
