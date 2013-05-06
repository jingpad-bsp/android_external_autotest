# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros.faftsequence import FAFTSequence
import logging
import time


class firmware_ECWatchdog(FAFTSequence):
    """
    Servo based EC watchdog test.
    """
    version = 1


    # Delay of spin-wait in ms. Should be long enough to trigger watchdog reset.
    WATCHDOG_DELAY = 3000

    # Delay of EC power on.
    EC_BOOT_DELAY = 1000


    def setup(self):
        super(firmware_ECWatchdog, self).setup()
        # Only run in normal mode
        self.setup_dev_mode(False)


    def reboot_by_watchdog(self):
        """
        Trigger a watchdog reset.
        """
        self.faft_client.system.run_shell_command("sync")
        self.ec.send_command("waitms %d" % self.WATCHDOG_DELAY)
        time.sleep((self.WATCHDOG_DELAY + self.EC_BOOT_DELAY) / 1000.0)
        self.check_lid_and_power_on()


    def run_once(self):
        if not self.check_ec_capability():
            raise error.TestNAError("Nothing needs to be tested on this device")
        self.register_faft_sequence((
            {   # Step 1, trigger a watchdog reset and power on system again.
                'reboot_action': self.reboot_by_watchdog,
            },
            {   # Step 2, dummy step to make sure step 1 reboots
            }
        ))
        self.run_faft_sequence()
