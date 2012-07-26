# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_DevMode(FAFTSequence):
    """
    Servo based developer firmware boot test.
    """
    version = 1


    def setup(self):
        super(firmware_DevMode, self).setup()
        self.setup_dev_mode(dev_mode=False)


    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step 1, enable dev mode
                'state_checker': (self.crossystem_checker, {
                    'devsw_boot': '0',
                    'mainfw_type': 'normal',
                }),
                'userspace_action': self.enable_dev_mode_and_fw,
                'reboot_action': None,
                'firmware_action': self.wait_fw_screen_and_ctrl_d,
            },
            {   # Step 2, expected developer mode boot and enable normal mode
                'state_checker': (self.crossystem_checker, {
                    'devsw_boot': '1',
                    'mainfw_type': 'developer',
                }),
                'userspace_action': self.enable_normal_mode_and_fw,
                'reboot_action': None,
            },
            {   # Step 3, expected normal mode boot, done
                'state_checker': (self.crossystem_checker, {
                    'devsw_boot': '0',
                    'mainfw_type': 'normal',
                }),
            }
        ))
        self.run_faft_sequence()
