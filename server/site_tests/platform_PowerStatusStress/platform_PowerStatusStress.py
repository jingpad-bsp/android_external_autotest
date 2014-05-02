# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re, time
from autotest_lib.server import test
from autotest_lib.client.common_lib import error

_CHARGING = 'CHARGING'
_DISCHARGING = 'DISCHARGING'

class platform_PowerStatusStress(test.test):
    version = 1

    def suspend_resume(self):
        pass

    def run_once(self, host, loop_count):

        #Start as powered on
        if host.has_power():
            host.power_on()
        else:
            raise error.TestFail('No RPM is setup to device')

        pdu_connected = True

        for i in xrange(loop_count * 2):
            time.sleep(1)
            iteration = i/2 + 1

            # Get power_supply_info output
            psi_output = host.run('power_supply_info').stdout.strip()
            psi_output = psi_output.replace('\n', '')

            if pdu_connected:
                expected_psi_online = 'yes'
                expected_psi_enum_type = 'AC'
                expected_psi_bat_state = '(Charging|Fully charged)'
            else:
                expected_psi_online = 'no'
                expected_psi_enum_type = 'Disconnected'
                expected_psi_bat_state = 'Discharging'

            is_psi_online = re.match(r'.+online:\s+%s.+' % expected_psi_online,
                                     psi_output) is not None
            is_psi_enum_type = re.match(r'.+enum type:\s+%s.+' %
                expected_psi_enum_type, psi_output) is not None
            is_psi_bat_state = re.match(r'.+state:\s+%s.+' %
                expected_psi_bat_state, psi_output) is not None

            if not all([is_psi_online,
                       is_psi_enum_type,
                       is_psi_bat_state]):
                host.power_on()
                raise error.TestFail('Bad %s state at iteration %d: %s' %
                    (_CHARGING if pdu_connected else _DISCHARGING,
                     iteration, psi_output))

            if pdu_connected:
                host.power_off()
                pdu_connected = False
            else:
                host.power_on()
                pdu_connected = True

            #TODO(kalin@): Add suspend/resume
            self.suspend_resume()

        #Finish as powered on
        host.power_on()
