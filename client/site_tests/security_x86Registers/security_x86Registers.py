# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import power_utils
from autotest_lib.client.cros import sys_power

MSR_POSITIVE = {
    'Atom': {
        # Empty: VMX does not exist on Atom.
        },
    'Non-Atom': {
        # IA32_FEATURE_CONTROL[2:0]
        #   0 - Lock bit (1 = locked)
        #   1 - Enable VMX in SMX operation
        #   2 - Enable VMX outside SMX operation
        # Want value "1": VMX locked and disabled in all modes.
        '0x3a':  [('2:0', 1)],
        },
    }

MSR_NEGATIVE = {
    'Atom': {
        # Empty: VMX does not exist on Atom.
        },
    'Non-Atom': {
        # Inverted from above: none of these bits should be set.
        '0x3a':  [('2:0', 6)],
        },
    }


class security_x86Registers(test.test):
    version = 1

    def _check_msr(self):
        errors = 0

        # Negative tests; make sure infrastructure is working.
        if self._registers.verify_msr(MSR_NEGATIVE[self._cpu_type]) == 0:
            logging.error('FAIL: inverted MSR tests did not fail!')
            errors += 1

        # Positive tests; make sure values are for real.
        errors += self._registers.verify_msr(MSR_POSITIVE[self._cpu_type])

        return errors

    def run_once(self):
        errors = 0

        cpu_arch = power_utils.get_x86_cpu_arch()
        if not cpu_arch:
            cpu_arch = utils.get_cpu_arch()
            if cpu_arch == "arm":
                logging.debug('ok: skipping x86-only test on %s.' % (cpu_arch))
                return
            raise error.TestNAError('Unsupported CPU: %s' % (cpu_arch))

        self._cpu_type = 'Atom'
        if cpu_arch is not 'Atom':
            self._cpu_type = 'Non-Atom'

        self._registers = power_utils.Registers()

        # Check running machine.
        errors += self._check_msr()

        # Pause briefly to make sure the RTC is ready for suspend/resume.
        time.sleep(3)
        # Suspend the system to RAM and return after 10 seconds.
        sys_power.do_suspend(10)

        # Check resumed machine.
        errors += self._check_msr()

        if errors > 0:
            raise error.TestFail("x86 register mismatch detected")
