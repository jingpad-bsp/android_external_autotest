# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft_classes import FAFTSequence

class firmware_ECKeyboard(FAFTSequence):
    """
    Servo based EC keyboard test.
    """
    version = 1


    # Delay between commands
    CMD_DELAY = 1


    def setup(self):
        super(firmware_ECKeyboard, self).setup()
        # Only run in normal mode
        self.setup_dev_mode(False)


    def switch_tty2(self):
        """Switch to tty2 console."""
        self.ec.key_down('<ctrl_l>')
        self.ec.key_down('<alt_l>')
        self.ec.key_down('<f2>')
        self.ec.key_up('<f2>')
        self.ec.key_up('<alt_l>')
        self.ec.key_up('<ctrl_l>')
        time.sleep(self.CMD_DELAY)


    def reboot_by_keyboard(self):
        """
        Simulate key press sequence to log into console and then issue reboot
        command.
        """
        self.switch_tty2()
        self.ec.send_key_string('root<enter>')
        time.sleep(self.CMD_DELAY)
        self.ec.send_key_string('test0000<enter>')
        time.sleep(self.CMD_DELAY)
        self.ec.send_key_string('reboot<enter>')


    def run_once(self):
        if not self.check_ec_capability(['keyboard']):
            raise error.TestNAError("Nothing needs to be tested on this device")
        self.register_faft_sequence((
            {   # Step 1, use key press simulation to issue reboot command
                'reboot_action': self.reboot_by_keyboard,
            },
            {   # Step 2, dummy step to ensure reboot
            }
        ))
        self.run_faft_sequence()
