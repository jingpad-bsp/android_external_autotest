# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_ECCorruptFwBodyA(FAFTSequence):
    """
    Servo based EC body A corruption test.
    """
    version = 1


    def ensure_fw_a_boot(self):
        """Ensure EC firmware A boot this time.

        If not, it may be a test failure during step 2 or 3, try to recover to
        firmware A boot by recovering the firmware and rebooting.
        """
        if not self.ec_act_copy_checker('A'):
            self.run_faft_step({
                'userspace_action': (self.faft_client.run_shell_command,
                    'chromeos-firmwareupdate --mode recovery'),
                'reboot_action': (self.sync_and_ec_reboot)
            })


    def setup(self, dev_mode=False):
        super(firmware_ECCorruptFwBodyA, self).setup()
        self.setup_dev_mode(dev_mode)
        self.ensure_fw_a_boot()


    def cleanup(self):
        self.ensure_fw_a_boot()
        super(firmware_ECCorruptFwBodyA, self).cleanup()


    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step 1, corrupt firmware body A
                'state_checker': (self.ec_act_copy_checker, 'A'),
                'userspace_action': (self.faft_client.corrupt_EC_body,
                                     'a'),
                'reboot_action': (self.sync_and_ec_reboot),
            },
            {   # Step 2, expected firmware B boot and restore firmware A
                'state_checker': (self.ec_act_copy_checker, 'B'),
                'userspace_action': (self.faft_client.restore_EC_body,
                                     'a'),
                'reboot_action': (self.sync_and_ec_reboot),
            },
            {   # Step 3, expected firmware A boot, done
                'state_checker': (self.ec_act_copy_checker, 'A'),
            },
        ))
        self.run_faft_sequence()
