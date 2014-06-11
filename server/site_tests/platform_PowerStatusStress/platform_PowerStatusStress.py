# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, re, time
from autotest_lib.server import test
from autotest_lib.client.common_lib import error

_CHARGING = 'CHARGING'
_DISCHARGING = 'DISCHARGING'
_WAIT_SECS_AFTER_SWITCH = 2

class platform_PowerStatusStress(test.test):
    version = 1

    def do_suspend_resume(self, suspend_time):
        logging.info('Suspending for %s sec' % suspend_time)
        self.host.run('echo 0 > /sys/class/rtc/rtc0/wakealarm')
        self.host.run('echo +%d > /sys/class/rtc/rtc0/wakealarm' %
                      suspend_time)
        self.host.run('powerd_dbus_suspend --delay=0 &')


    def cleanup(self):
        # Finish as powered on
        self.host.power_on()


    def switch_power_and_verify(self, powered_on, expected):
        if powered_on:
            self.host.power_on()
        else:
            self.host.power_off()
        time.sleep(_WAIT_SECS_AFTER_SWITCH)

        # Get power_supply_info output
        psi_output = self.host.run('power_supply_info').stdout.strip()
        psi_output = psi_output.replace('\n', '')

        exp_psi_online, exp_psi_enum_type, exp_psi_bat_state = expected

        is_psi_online = re.match(r'.+online:\s+%s.+' % exp_psi_online,
                                 psi_output) is not None
        is_psi_enum_type = re.match(r'.+enum type:\s+%s.+' % exp_psi_enum_type,
                                    psi_output) is not None
        is_psi_bat_state = re.match(r'.+state:\s+%s.+' % exp_psi_bat_state,
                                    psi_output) is not None

        if not all([is_psi_online, is_psi_enum_type, is_psi_bat_state]):
            raise error.TestFail('Bad %s state: %s' %
                (_CHARGING if powered_on else _DISCHARGING,
                 psi_output))


    def run_once(self, host, loop_count, suspend_time):
        self.host = host

        # Start as powered on
        if self.host.has_power():
            self.host.power_on()
        else:
            raise error.TestFail('No RPM is setup to device')

        pdu_connected = True
        for i in xrange(loop_count):
            logging.info('Iteration %d' % (i + 1))

            # Suspend/resume
            if suspend_time != -1:
                self.do_suspend_resume(suspend_time)
                time.sleep(1)

            # Charging state
            expected = ('yes', 'AC', '(Charging|Fully charged)')
            self.switch_power_and_verify(True, expected)

            # Discharging state
            expected = ('no', 'Disconnected', 'Discharging')
            self.switch_power_and_verify(False, expected)