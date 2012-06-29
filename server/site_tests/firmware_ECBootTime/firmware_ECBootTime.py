# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faftsequence import FAFTSequence

class firmware_ECBootTime(FAFTSequence):
    """
    Servo based EC boot time test.
    """
    version = 1

    def check_boot_time(self):
        reboot = self.send_uart_command_get_output("reboot",
                "([0-9\.]+) idle task started")
        power_press = self.send_uart_command_get_output("powerbtn",
                "\[([0-9\.]+) PB pressed\]")
        firmware_resp = self.send_uart_command_get_output("",
                "([0-9\.]+) Port 80")
        reboot_time = float(reboot[0].group(1))
        power_press_time = float(power_press[0].group(1))
        firmware_resp_time = float(firmware_resp[0].group(1))
        boot_time = firmware_resp_time - power_press_time
        logging.info("EC cold boot time: %f s" % reboot_time)
        if reboot_time > 1.0:
            raise error.TestFail("EC cold boot time longer than 1 second.")
        logging.info("EC boot time: %f s" % boot_time)
        if boot_time > 1.0:
            raise error.TestFail("Boot time longer than 1 second.")

    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step 1, Reboot and check EC cold boot time and host boot time
                'reboot_action': self.check_boot_time,
            },
            {   # Step 2, dummy step to make step 1 reboot
            }
        ))
        self.run_faft_sequence()
