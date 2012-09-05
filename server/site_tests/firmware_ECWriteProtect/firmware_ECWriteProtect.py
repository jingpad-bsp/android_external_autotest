# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_ECWriteProtect(FAFTSequence):
    """
    Servo based EC write protect test.
    """
    version = 1


    def ensure_fw_a_boot(self):
        """Ensure firmware A boot this time."""
        if not self.crossystem_checker({'mainfw_act': 'A', 'tried_fwb': '0'}):
            self.run_faft_step({
                'userspace_action': (self.faft_client.run_shell_command,
                    'chromeos-firmwareupdate --mode recovery')
            })


    def write_protect_checker(self):
        """Checker that ensure the following write protect flags are set:
            - wp_gpio_asserted
            - ro_at_boot
            - ro_now
            - all_now
        """
        try:
            self.send_uart_command_get_output("flashinfo",
                    "Flags:\s+wp_gpio_asserted\s+ro_at_boot\s+ro_now\s+all_now",
                    timeout=0.1)
            return True
        except error.TestFail:
            # Didn't get expected flags
            return False


    def setup(self, dev_mode=False):
        super(firmware_ECWriteProtect, self).setup()
        self.setup_dev_mode(dev_mode)
        self.ensure_fw_a_boot()


    def cleanup(self):
        self.ensure_fw_a_boot()
        super(firmware_ECWriteProtect, self).cleanup()


    def run_once(self, host=None):
        flags = self.faft_client.get_firmware_flags('a')
        if flags & self.PREAMBLE_USE_RO_NORMAL == 0:
            logging.info('The firmware USE_RO_NORMAL flag is disabled.')
            return

        self.register_faft_sequence((
            {   # Step 1, expected EC RO boot, enable WP and reboot EC.
                'state_checker': (self.ro_normal_checker, 'A'),
                'reboot_action': (self.set_EC_write_protect_and_reboot, True),
            },
            {   # Step 2, expected EC RO boot, write protected. Disable RO flag
                #         and reboot EC.
                'state_checker': (lambda: self.ro_normal_checker('A') and
                                          self.write_protect_checker()),
                'userspace_action': (self.faft_client.set_firmware_flags,
                                     'a', 0),
                'reboot_action': self.sync_and_cold_reboot,
            },
            {   # Step 3, expected EC RW boot, write protected. Reboot EC by
                #         ectool.
                'state_checker': (lambda: self.ro_normal_checker('A',
                                              twostop=True) and
                                          self.write_protect_checker()),
                'reboot_action': (self.sync_and_ec_reboot, 'cold'),
            },
            {   # Step 4, expected EC RW boot, write protected. Restore RO
                #         normal flag and deactivate write protect.
                'state_checker': (lambda: self.ro_normal_checker('A',
                                              twostop=True) and
                                          self.write_protect_checker()),
                'userspace_action': (self.faft_client.set_firmware_flags,
                                     'a', self.PREAMBLE_USE_RO_NORMAL),
                'reboot_action': (self.set_EC_write_protect_and_reboot, False),
            },
            {   # Step 5, expected EC RO boot.
                'state_checker': (self.ro_normal_checker, 'A'),
            },
        ))
        self.run_faft_sequence()
