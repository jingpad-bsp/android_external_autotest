# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob, os
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils

class power_ProbeDriver(test.test):
    version = 1
    power_supply_path = '/sys/class/power_supply/*'

    def run_once(self, test_which='Mains'):
        ac_paths  = []
        bat_paths = []
        # Gather power supplies
        for path in glob.glob(power_ProbeDriver.power_supply_path):
            type_path = os.path.join(path, 'type')
            if not os.path.exists(type_path):
                continue
            type = utils.read_one_line(type_path)
            if type == 'Mains':
                ac_paths.append(path)
            elif type == 'Battery':
                bat_paths.append(path)
        run_dict = { 'Mains': self.run_ac, 'Battery': self.run_bat }
        run = run_dict.get(test_which)
        if run:
            run(ac_paths, bat_paths)
        else:
            raise error.TestNAError('Unknown test type: %s' % test_which)

    def run_ac(self, ac_paths, bat_paths):
        if len(ac_paths) != 1:
            raise error.TestFail('Not exactly one AC found: %d' %
                                 len(ac_paths))

        if not self._online(ac_paths[0]):
            raise error.TestFail('AC is not online: %s' % ac_paths[0])

        # if there are batteries, test fails if one of them is discharging
        # note: any([]) == False, so we don't have to test len(bat_paths) > 0
        if any(self._read_status(bat_path) == 'Discharging'
               for bat_path in bat_paths
               if self._present(bat_path)):
            raise error.TestFail('One of batteries is discharging')

    def run_bat(self, ac_paths, bat_paths):
        if len(bat_paths) == 0:
            raise error.TestFail('Find no batteries')

        presented = [bat_path for bat_path in bat_paths
                     if self._present(bat_path)]
        if len(presented) == 0:
            raise error.TestFail('No batteries are presented')

        if all(self._read_status(bat_path) != 'Discharging'
               for bat_path in presented):
            raise error.TestFail('No batteries are discharging')

        if any(self._online(ac_path) for ac_path in ac_paths):
            raise error.TestFail('One of ACs is online')

    def _online(self, ac_path):
        online_path = os.path.join(ac_path, 'online')
        if not os.path.exists(online_path):
            raise error.TestFail('online path does not exist: %s' % online_path)
        online = utils.read_one_line(online_path)
        return online == '1'

    def _present(self, bat_path):
        present_path = os.path.join(bat_path, 'present')
        if not os.path.exists(present_path):
            return False
        return utils.read_one_line(present_path) == '1'

    def _read_status(self, bat_path):
        status_path = os.path.join(bat_path, 'status')
        if not os.path.exists(status_path):
            raise error.TestNAError('Status not found: %s' % status_path)
        return utils.read_one_line(status_path)
