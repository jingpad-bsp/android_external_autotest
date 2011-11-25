# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_DevMode(FAFTSequence):
    """
    Servo based developer firmware boot test.
    """
    version = 1


    # The devsw off->on transition states are different based on platforms.
    # For Alex/ZGB, it is dev switch on but normal firmware boot.
    # For other platforms, it is dev switch on and developer firmware boot.
    def check_devsw_on_transition(self, fwb_tries='0'):
        fwid = self.faft_client.get_crossystem_value('fwid').lower()
        if fwid.startswith('alex') or fwid.startswith('zgb'):
            return self.crossystem_checker({
                    'devsw_boot': '1',
                    'mainfw_act': 'A' if fwb_tries == '0' else 'B',
                    'mainfw_type': 'normal',
                    'tried_fwb': fwb_tries,
                })
        else:
            return self.crossystem_checker({
                    'devsw_boot': '1',
                    'mainfw_act': 'A' if fwb_tries == '0' else 'B',
                    'mainfw_type': 'developer',
                    'tried_fwb': fwb_tries,
                })


    # The devsw on->off transition states are different based on platforms.
    # For Alex/ZGB, it is firmware B normal boot. Firmware A is still developer.
    # For other platforms, it is directly firmware A normal boot.
    def check_devsw_off_transition(self, fwb_tries='0'):
        fwid = self.faft_client.get_crossystem_value('fwid').lower()
        if fwid.startswith('alex') or fwid.startswith('zgb'):
            return self.crossystem_checker({
                    'devsw_boot': '0',
                    'mainfw_act': 'B',
                    'mainfw_type': 'normal',
                    'tried_fwb': fwb_tries,
                })
        else:
            return self.crossystem_checker({
                    'devsw_boot': '0',
                    'mainfw_act': 'A' if fwb_tries == '0' else 'B',
                    'mainfw_type': 'normal',
                    'tried_fwb': fwb_tries,
                })


    def setup(self):
        super(firmware_DevMode, self).setup()
        self.setup_dev_mode(dev_mode=False)
        self.setup_tried_fwb(tried_fwb=False)


    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step 1, enable dev mode
                'state_checker': (self.crossystem_checker, {
                    'devsw_boot': '0',
                    'mainfw_act': 'A',
                    'mainfw_type': 'normal',
                }),
                'userspace_action': self.servo.enable_development_mode,
                'firmware_action': self.wait_fw_screen_and_ctrl_d,
            },
            {   # Step 2, expected values based on platforms (see above),
                # and set fwb_tries flag.
                'state_checker': (self.check_devsw_on_transition, '0'),
                'userspace_action': self.faft_client.set_try_fw_b,
                'firmware_action': self.wait_fw_screen_and_ctrl_d,
            },
            {
                # Step 3, expected the same state,
                # and run "chromeos-firmwareupdate --mode todev && reboot".
                'state_checker': (self.check_devsw_on_transition, '1'),
                'userspace_action': (self.faft_client.run_shell_command,
                    'chromeos-firmwareupdate --mode todev && reboot'),
                # Ignore the default reboot_action here because the
                # userspace_action (firmware updater) will reboot the system.
                'reboot_action': None,
                'firmware_action': self.wait_fw_screen_and_ctrl_d,
            },
            {   # Step 4, expected developer mode boot and disable dev switch
                'state_checker': (self.crossystem_checker, {
                    'devsw_boot': '1',
                    'mainfw_act': 'A',
                    'mainfw_type': 'developer',
                }),
                'userspace_action': self.servo.disable_development_mode,
            },
            {   # Step 5, expected values based on platforms (see above),
                # and set fwb_tries flag.
                'state_checker': (self.check_devsw_off_transition, '0'),
                'userspace_action': self.faft_client.set_try_fw_b,
            },
            {   # Step 6, expected the same state,
                # and run "chromeos-firmwareupdate --mode tonormal && reboot".
                'state_checker': (self.check_devsw_off_transition, '1'),
                'userspace_action': (self.faft_client.run_shell_command,
                    'chromeos-firmwareupdate --mode tonormal && reboot'),
                'reboot_action': None,
            },
            {   # Step 7, expected normal mode boot, done
                'state_checker': (self.crossystem_checker, {
                    'devsw_boot': '0',
                    'mainfw_act': 'A',
                    'mainfw_type': 'normal',
                }),
            }
        ))
        self.run_faft_sequence()
