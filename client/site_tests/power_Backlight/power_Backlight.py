# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time, utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, site_power_status, site_ui, \
                                           utils

class power_Backlight(test.test):
    version = 1


    def run_once(self, delay=60, seconds=10, tries=20):
        # disable screen locker and powerd
        os.system('stop screen-locker')
        os.system('stop powerd')

        # disable screen blanking. Stopping screen-locker isn't
        # synchronous :(. Add a sleep for now, till powerd comes around
        # and fixes all this for us.
        # TODO(davidjames): Power manager should support this feature directly
        time.sleep(5)
        site_ui.xsystem('xset s off')
        site_ui.xsystem('xset dpms 0 0 0')
        site_ui.xsystem('xset -dpms')

        status = site_power_status.get_status()
        if status.linepower[0].online:
            raise error.TestFail('Machine must be unplugged')

        cmd = 'backlight-tool --get_max_brightness'
        max_brightness = int(utils.system_output(cmd).rstrip())
        if max_brightness < 4:
            raise error.TestFail('Must have at least 5 backlight levels')
        keyvals = {}
        rates = []
        
        levels = [0, int(0.25*max_brightness), int(0.5*max_brightness),
                  int(0.75*max_brightness), max_brightness]
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
        os.system('start screen-locker')

