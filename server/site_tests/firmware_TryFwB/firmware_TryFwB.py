# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_TryFwB(FAFTSequence):
    """
    Servo based RW firmware B boot test.
    """
    version = 1

    def ensure_fw_a_boot(self):
        """Ensure firmware A boot this time.

        If not, it may be a test failure during step 2, try to recover to
        firmware A boot by recovering the firmware and rebooting.
        """
        if not self.crossystem_checker({'mainfw_act': 'A', 'tried_fwb': '0'}):
            self.faft_client.software_reboot()
            self.wait_for_client_offline()
            self.wait_for_client()


    def setup(self):
        super(firmware_TryFwB, self).setup()
        self.ensure_fw_a_boot()


    def cleanup(self):
        self.ensure_fw_a_boot()
        super(firmware_TryFwB, self).cleanup()


    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step 1, set fwb_tries flag
                'state_checker': (self.crossystem_checker, {
                    'mainfw_act': 'A',
                    'tried_fwb': '0',
                }),
                'userspace_action': self.faft_client.set_try_fw_b,
            },
            {   # Step 2, expected firmware B boot, reboot
                'state_checker': (self.crossystem_checker, {
                    'mainfw_act': 'B',
                    'tried_fwb': '1',
                }),
            },
            {   # Step 3, expected firmware A boot, done
                'state_checker': (self.crossystem_checker, {
                    'mainfw_act': 'A',
                    'tried_fwb': '0',
                }),
            },
        ))
        self.run_faft_sequence()
