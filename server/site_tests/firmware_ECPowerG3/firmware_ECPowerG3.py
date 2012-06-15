# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faftsequence import FAFTSequence

class firmware_ECPowerG3(FAFTSequence):
    """
    Servo based EC X86 power G3 drop test.
    """
    version = 1

    # Time out range for waiting system drop into G3.
    G3_DELAY = 13

    # Record failure event
    _failed = False

    def check_G3(self):
        """Shutdown the system and check if X86 drop into G3 correctly."""
        self.faft_client.run_shell_command("shutdown -P now")
        self.send_uart_command_get_output("", "x86 power state 1 = S5")
        try:
                self.send_uart_command_get_output("", "x86 power state 0 = G3",
                                                   timeout=self.G3_DELAY)
        except:
                # Catch failure here to gracefully terminate test
                logging.error("EC fails to drop into G3")
                self._failed = True
        self.servo.power_short_press()


    def check_failure(self):
        return not self._failed


    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step 1, power off and check if system drop into G3 correctly
                'reboot_action': self.check_G3,
            },
            {   # Step 2, check if failure occurred
                'state_checker': self.check_failure,
            }
        ))
        self.run_faft_sequence()
