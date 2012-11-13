# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui, power_status

class power_Backlight(test.test):
    version = 1


    def run_once(self, delay=60, seconds=10, tries=20):
        # disable powerd
        os.system('stop powerd')

        # disable screen blanking. Stopping screen-locker isn't
        # synchronous :(. Add a sleep for now, till powerd comes around
        # and fixes all this for us.
        # TODO(davidjames): Power manager should support this feature directly
        time.sleep(5)
        cros_ui.xsystem('LD_LIBRARY_PATH=/usr/local/lib ' + 'xset s off')
        cros_ui.xsystem('LD_LIBRARY_PATH=/usr/local/lib ' + 'xset dpms 0 0 0')
        cros_ui.xsystem('LD_LIBRARY_PATH=/usr/local/lib ' + 'xset -dpms')

        status = power_status.get_status()
        if status.linepower[0].online:
            raise error.TestFail('Machine must be unplugged')

        cmd = 'backlight-tool --get_max_brightness'
        max_brightness = int(utils.system_output(cmd).rstrip())
        if max_brightness < 4:
            raise error.TestFail('Must have at least 5 backlight levels')
        sysfs_max = self._get_highest_sysfs_max_brightness()
        if max_brightness != sysfs_max:
            raise error.TestFail(('Max brightness %d is not the highest ' +
                                  'possible |max_brightness|, which is %d') %
                                 (max_brightness, sysfs_max))
        keyvals = {}
        rates = []

        levels = [0, int(0.5*max_brightness), max_brightness]
        for i in levels:
            utils.system('backlight-tool --set_brightness %d' % i)
            time.sleep(delay)
            this_rate = []
            for j in range(tries):
                time.sleep(seconds)
                status.refresh()
                this_rate.append(status.battery[0].energy_rate)
            rate = min(this_rate)
            keyvals['w_bl_%d_rate' % i] = rate
            rates.append(rate)
        self.write_perf_keyval(keyvals)
        for i in range(1, len(levels)):
            if rates[i] <= rates[i-1]:
                raise error.TestFail('Turning up the backlight ' \
                                     'should increase energy consumption')


    def cleanup(self):
        # Re-enable screen locker and powerd. This also re-enables dpms.
        os.system('start powerd')


    def _get_highest_sysfs_max_brightness(self):
        # Print |max_brightness| for all backlight sysfs directories, and return
        # the highest of these max_brightness values.
        cmd = 'cat /sys/class/backlight/*/max_brightness'
        output = utils.system_output(cmd)
        return max(map(int, output.split()))
