# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, site_power_status


class power_BatteryCharge(test.test):
    version = 1

    def initialize(self):
        self.status = site_power_status.get_status()

        if not self.on_ac():
            raise error.TestNAError(
                  'This test needs to be run with the AC power online')


    def run_once(self, max_run_time=180, percent_charge_to_add=1,
                 percent_initial_charge_max=None,
                 percent_target_charge=None):
        """
        max_run_time: maximum time the test will run for
        percent_charge_to_add: percentage of the design capacity charge to
                  add. The target charge will be capped at the design capacity.
        percent_initial_charge_max: maxium allowed initial charge.
        """

        time_to_sleep = 60
        self.remaining_time = self.max_run_time = max_run_time

        self.charge_full_design = self.status.battery[0].charge_full_design
        self.initial_charge = self.status.battery[0].charge_now
        percent_initial_charge = self.initial_charge * 100 / \
                                 self.charge_full_design
        if percent_initial_charge_max and percent_initial_charge > \
                                          percent_initial_charge_max:
            raise error.TestError('Initial charge (%f) higher than max (%f)'
                      % (percent_initial_charge, percent_initial_charge_max))

        current_charge = self.initial_charge
        if percent_target_charge is None:
            charge_to_add = self.charge_full_design * \
                            float(percent_charge_to_add) / 100
            target_charge = current_charge + charge_to_add
        else:
            target_charge = self.charge_full_design * \
                            float(percent_target_charge) / 100

        # trim target_charge if it exceeds designed capacity
        if target_charge > self.charge_full_design:
            target_charge = self.charge_full_design

        logging.info('max_run_time: %d' % self.max_run_time)
        logging.info('initial_charge: %f' % self.initial_charge)
        logging.info('target_charge: %f' % target_charge)

        while self.remaining_time and current_charge < target_charge:
            if time_to_sleep > self.remaining_time:
                time_to_sleep = self.remaining_time
            self.remaining_time -= time_to_sleep

            time.sleep(time_to_sleep)

            self.status.refresh()
            if not self.on_ac():
                raise error.TestError(
                      'This test needs to be run with the AC power online')

            new_charge = self.status.battery[0].charge_now
            logging.info('time_to_sleep: %d' % time_to_sleep)
            logging.info('charge_added: %f' % (new_charge - current_charge))

            current_charge = new_charge
            logging.info('current_charge: %f' % current_charge)


    def postprocess_iteration(self):
        keyvals = {}
        keyvals['ah_charge_full'] = self.status.battery[0].charge_full
        keyvals['ah_charge_full_design'] = self.charge_full_design
        keyvals['ah_initial_charge'] = self.initial_charge
        keyvals['ah_final_charge'] = self.status.battery[0].charge_now
        keyvals['s_time_taken'] = self.max_run_time - self.remaining_time
        keyvals['percent_initial_charge'] = self.initial_charge * 100 / \
                                            keyvals['ah_charge_full_design']
        keyvals['percent_final_charge'] = keyvals['ah_final_charge'] * 100 / \
                                          keyvals['ah_charge_full_design']

        self.write_perf_keyval(keyvals)


    def on_ac(self):
        return self.status.linepower[0].online
