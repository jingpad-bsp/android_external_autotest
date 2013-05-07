# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_ECWriteProtect(FAFTSequence):
    """
    Servo based EC write protect test.
    """
    version = 1


    def write_protect_checker(self):
        """Checker that ensure the following write protect flags are set:
            - wp_gpio_asserted
            - ro_at_boot
            - ro_now
            - all_now
        """
        try:
            self.ec.send_command_get_output("flashinfo",
                  ["Flags:\s+wp_gpio_asserted\s+ro_at_boot\s+ro_now\s+all_now"])
            return True
        except error.TestFail:
            # Didn't get expected flags
            return False


    def setup(self, dev_mode=False):
        super(firmware_ECWriteProtect, self).setup(ec_wp=False)
        self.backup_firmware()
        self.setup_dev_mode(dev_mode)
        self.ec.send_command("chan 0")


    def cleanup(self):
        self.ec.send_command("chan 0xffffffff")
        self.restore_firmware()
        super(firmware_ECWriteProtect, self).cleanup()


    def run_once(self):
        flags = self.faft_client.bios.get_preamble_flags('a')
        if flags & vboot.PREAMBLE_USE_RO_NORMAL == 0:
            logging.info('The firmware USE_RO_NORMAL flag is disabled.')
            return

        self.register_faft_sequence((
            {   # Step 1, expected EC RO boot, enable WP and reboot EC.
                'state_checker': (self.checkers.ro_normal_checker, 'A'),
                'reboot_action': (self.set_ec_write_protect_and_reboot, True),
            },
            {   # Step 2, expected EC RO boot, write protected. Disable RO flag
                #         and reboot EC.
                'state_checker': [(self.checkers.ro_normal_checker, 'A'),
                                  self.write_protect_checker],
                'userspace_action': (self.faft_client.bios.set_preamble_flags,
                                     ('a', 0)),
                'reboot_action': self.sync_and_cold_reboot,
            },
            {   # Step 3, expected EC RW boot, write protected. Reboot EC by
                #         ectool.
                'state_checker': [(self.checkers.ro_normal_checker,
                                   ('A', True)),
                                  self.write_protect_checker],
                'reboot_action': (self.sync_and_ec_reboot, 'hard'),
            },
            {   # Step 4, expected EC RW boot, write protected. Restore RO
                #         normal flag and deactivate write protect.
                'state_checker': [(self.checkers.ro_normal_checker,
                                   ('A', True)),
                                  self.write_protect_checker],
                'userspace_action': (self.faft_client.bios.set_preamble_flags,
                                     ('a', vboot.PREAMBLE_USE_RO_NORMAL)),
                'reboot_action': (self.set_ec_write_protect_and_reboot, False),
            },
            {   # Step 5, expected EC RO boot.
                'state_checker': (self.checkers.ro_normal_checker, 'A'),
            },
        ))
        self.run_faft_sequence()
