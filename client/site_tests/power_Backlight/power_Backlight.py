# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time, utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, site_power_status, site_ui, \
                                           utils


class power_Backlight(test.test):
    version = 1


    def run_once(self, seconds=120):
        # disable screen locker and screen blanking
        # TODO(davidjames): Power manager should support this feature directly
        os.system('stop screen-locker')
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
            time.sleep(seconds)
            status.refresh()
            keyvals['w_bl_%d_rate' % i] = status.battery[0].energy_rate
            rates.append(status.battery[0].energy_rate)
        self.write_perf_keyval(keyvals)
        for i in range(1, len(levels)):
            if rates[i] <= rates[i-1]:
                raise error.TestFail('Turning up the backlight ' \
                                     'should increase energy consumption')


    def cleanup(self):
        # re-enable screen locker and screen blanking
        utils.system('start screen-locker')
        site_ui.xsystem('xset +dpms')

