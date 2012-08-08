# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_RONormalBoot(FAFTSequence):
    """
    Servo based firmware RO normal boot test.

    This test only runs on the firmware on which its firmware preamble flags
    have USE_RO_NORMAL enabled. Since we always build and pack a workable
    RW firmware in the RW firmware body section, although it is not used when
    the USE_RO_NORMAL flag is enabled.

    On runtime, the test disables the RO normal boot flag in the current
    firmware and checks its next boot result.
    """
    version = 1

    PREAMBLE_USE_RO_NORMAL = 1


    def ensure_fw_a_boot(self):
        """Ensure firmware A boot this time."""
        if not self.crossystem_checker({'mainfw_act': 'A', 'tried_fwb': '0'}):
            self.run_faft_step({
                'userspace_action': (self.faft_client.run_shell_command,
                    'chromeos-firmwareupdate --mode recovery')
            })


    def setup(self, dev_mode=False):
        super(firmware_RONormalBoot, self).setup()
        self.setup_dev_mode(dev_mode)
        self.ensure_fw_a_boot()


    def cleanup(self):
        self.ensure_fw_a_boot()
        super(firmware_RONormalBoot, self).cleanup()


    def run_once(self, host=None):
        flags = self.faft_client.get_firmware_flags('a')
        if flags & self.PREAMBLE_USE_RO_NORMAL:
            self.register_faft_sequence((
                {   # Step 1, disable the RO normal boot flag
                    'state_checker': (self.crossystem_checker, {
                        'mainfw_act': 'A',
                        'tried_fwb': '0',
                    }),
                    'userspace_action': (self.faft_client.set_firmware_flags,
                                         'a',
                                         flags ^ self.PREAMBLE_USE_RO_NORMAL),
                },
                {   # Step 2, expected boot ok, restore the original flags
                    'state_checker': (self.crossystem_checker, {
                        'mainfw_act': 'A',
                        'tried_fwb': '0',
                    }),
                    'userspace_action': (self.faft_client.set_firmware_flags,
                                         'a',
                                         flags),
                },
                {   # Step 3, done
                    'state_checker': (self.crossystem_checker, {
                        'mainfw_act': 'A',
                        'tried_fwb': '0',
                    }),
                },
            ))
            self.run_faft_sequence()
        else:
            logging.info('The firmware USE_RO_NORMAL flag is disabled.')
