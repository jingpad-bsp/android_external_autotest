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
        if any(self._is_discharging(bat_path, ac_paths)
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

        if all(not self._is_discharging(bat_path, ac_paths) for bat_path
               in presented):
            raise error.TestFail('No batteries are discharging')

        if any(self._online(ac_path) for ac_path in ac_paths):
            raise error.TestFail('One of ACs is online')

    def _online(self, ac_path):
        online_path = os.path.join(ac_path, 'online')
        if not os.path.exists(online_path):
            raise error.TestFail('online path does not exist: %s' % online_path)
        online = utils.read_one_line(online_path)
        return online == '1'

    def _has_property(self, bat_path, field):
        """
        Indicates whether a battery sysfs has the given field.

        Fields:
        str     bat_path:           Battery sysfs path
        str     field:              Sysfs field to test for.

        Return value:
        bool    True if the field exists, False otherwise.
        """
        return os.path.exists(os.path.join(bat_path, field))

    def _read_property(self, bat_path, field):
        """
        Reads the contents of a sysfs field for a battery sysfs.

        Fields:
        str     bat_path:           Battery sysfs path
        str     field:              Sysfs field to read.

        Return value:
        str     The contents of the sysfs field.
        """
        property_path = os.path.join(bat_path, field)
        if not self._has_property(bat_path, field):
            raise error.TestNAError('Path not found: %s' % property_path)
        return utils.read_one_line(property_path)

    def _present(self, bat_path):
        """
        Indicates whether a battery is present, based on sysfs status.

        Fields:
        str     bat_path:           Battery sysfs path

        Return value:
        bool    True if the battery is present, False otherwise.
        """
        return self._read_property(bat_path, 'present') == '1'

    def _is_discharging(self, bat_path, ac_paths):
        """
        Indicates whether a battery is discharging, based on sysfs status.

        Sometimes the sysfs will not show status='Discharging' when actually
        discharging.  So this function looks at both battery sysfs and AC sysfs.
        If the battery is discharging, there will be no line power and the
        power/current draw will be nonzero.

        Fields:
        str     bat_path:           Battery sysfs path
        str[]   ac_paths:           List of AC sysfs paths

        Return value:
        bool    True if the battery is discharging, False otherwise.
        """
        if self._read_property(bat_path, 'status') == 'Discharging':
            return True
        if all(not self._online(ac_path) for ac_path in ac_paths):
            if (self._has_property(bat_path, 'power_now') and
                self._read_property(bat_path, 'power_now') != '0'):
                return True
            if (self._has_property(bat_path, 'current_now') and
                self._read_property(bat_path, 'current_now') != '0'):
                return True
        return False
