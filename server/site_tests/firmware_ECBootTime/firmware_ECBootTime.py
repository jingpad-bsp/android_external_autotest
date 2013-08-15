# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft.faft_classes import FAFTSequence

class firmware_ECBootTime(FAFTSequence):
    """
    Servo based EC boot time test.
    """
    version = 1

    def setup(self):
        super(firmware_ECBootTime, self).setup()
        # Only run in normal mode
        self.setup_dev_mode(False)


    def check_boot_time(self):
        """Check EC and AP boot times"""
        # Initialize a list of two strings, one printed by the EC when the AP
        # is taken out of reset, and another one printed when the EC observes
        # the AP running. These strings are used as for console output anchors
        # when calculating the AP boot time.
        #
        # This is very approximate, a better long term solution would be to
        # have the EC print the same fixed strings for these two events on all
        # platforms. http://crosbug.com/p/21628 has been opened to track this
        # issue.
        if self._x86:
            boot_anchors = ["\[([0-9\.]+) PB", "\[([0-9\.]+) Port 80"]
        else:
            boot_anchors = ["\[([0-9\.]+) AP running ...",
                            "\[([0-9\.]+) XPSHOLD seen"]
        power_cmd = "powerbtn" if self._x86 else "power on"
        reboot = self.ec.send_command_get_output(
            "reboot ap-off",
            ["([0-9\.]+) Inits done"])
        power_press = self.ec.send_command_get_output(
            power_cmd, boot_anchors)
        reboot_time = float(reboot[0][1])
        power_press_time = float(power_press[0][1])
        firmware_resp_time = float(power_press[1][1])
        boot_time = firmware_resp_time - power_press_time
        logging.info("EC cold boot time: %f s", reboot_time)
        if reboot_time > 1.0:
            raise error.TestFail("EC cold boot time longer than 1 second.")
        logging.info("EC boot time: %f s", boot_time)
        if boot_time > 1.0:
            raise error.TestFail("Boot time longer than 1 second.")


    def run_once(self):
        if not self.check_ec_capability():
            raise error.TestNAError("Nothing needs to be tested on this device")
        self._x86 = ('x86' in self.faft_config.ec_capability)
        dev_mode = self.checkers.crossystem_checker({'devsw_boot': '1'})
        self.register_faft_sequence((
            {   # Step 1, Reboot and check EC cold boot time and host boot time
                'reboot_action': self.check_boot_time,
                'firmware_action': (self.wait_fw_screen_and_ctrl_d
                                    if dev_mode else None)
            },
            {   # Step 2, dummy step to make step 1 reboot
            }
        ))
        self.run_faft_sequence()
