# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft.faft_classes import FAFTSequence

class firmware_ECPowerG3(FAFTSequence):
    """
    Servo based EC X86 power G3 drop test.
    """
    version = 1

    # Time out range for waiting system drop into G3.
    G3_RETRIES = 13

    # Record failure event
    _failed = False


    def setup(self):
        super(firmware_ECPowerG3, self).setup()
        # Only run in normal mode
        self.setup_dev_mode(False)
        self.ec.send_command("chan 0")


    def cleanup(self):
        self.ec.send_command("chan 0xffffffff")
        super(firmware_ECPowerG3, self).cleanup()


    def wait_power(self, reg_ex, retries):
        """
        Wait for certain power state.

        @param reg_ex: Acceptable "powerinfo" response. Can be a regex.
        @param retries: retries.
        """
        logging.info('Checking for "%s" maximum %d times.', reg_ex, retries)
        while retries > 0:
            try:
                retries = retries - 1
                self.ec.send_command_get_output("powerinfo", [reg_ex])
                return True
            except error.TestFail:
                pass
        return False


    def check_G3(self):
        """Shutdown the system and check if X86 drop into G3 correctly."""
        self.faft_client.system.run_shell_command("shutdown -P now")
        if not self.wait_power("x86 power state 0 = G3", self.G3_RETRIES):
            logging.error("EC fails to drop into G3")
            self._failed = True
        self.servo.power_short_press()


    def check_failure(self):
        return not self._failed


    def run_once(self):
        if not self.check_ec_capability(['x86']):
            raise error.TestNAError("Nothing needs to be tested on this device")
        self.register_faft_sequence((
            {   # Step 1, power off and check if system drop into G3 correctly
                'reboot_action': self.check_G3,
            },
            {   # Step 2, check if failure occurred
                'state_checker': self.check_failure,
            }
        ))
        self.run_faft_sequence()
