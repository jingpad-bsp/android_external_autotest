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

    FIRMWARE_SCREEN_DELAY = 10


    def ensure_normal_boot(self):
        """Ensure normal boot this time.

        If not, it may be a test failure during step 2, try to recover to
        normal mode by recovering the firmware and rebooting.
        """
        if not self.crossystem_checker({'devsw_boot': '0', 'mainfw_act': 'A',
                'mainfw_type': 'normal'}):
            self.servo.disable_development_mode()
            self.faft_client.run_shell_command(
                    'chromeos-firmwareupdate --mode tonormal')
            self.wait_for_client_offline()
            self.wait_for_client()


    def setup(self):
        super(firmware_DevMode, self).setup()
        self.ensure_normal_boot()


    def cleanup(self):
        self.ensure_normal_boot()
        super(firmware_DevMode, self).cleanup()


    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step 1, enable dev mode
                'state_checker': (self.crossystem_checker, {
                    'devsw_boot': '0',
                    'mainfw_act': 'A',
                    'mainfw_type': 'normal',
                }),
                'userspace_action': self.servo.enable_development_mode,
                'firmware_action': self.wait_and_ctrl_d,
            },
            {   # Step 2, expected values based on platforms (see below),
                # and run "chromeos-firmwareupdate --mode todev"
                'state_checker': self.check_devsw_on_transition,
                'userspace_action': (self.faft_client.run_shell_command,
                    'chromeos-firmwareupdate --mode todev'),
                'reboot_action': None,
                'firmware_action': self.wait_and_ctrl_d,
            },
            {   # Step 3, expected developer mode boot and disable dev switch
                'state_checker': (self.crossystem_checker, {
                    'devsw_boot': '1',
                    'mainfw_act': 'A',
                    'mainfw_type': 'developer',
                }),
                'userspace_action': self.servo.disable_development_mode,
            },
            {   # Step 4, expected values based on platforms (see below),
                # and run "chromeos-firmwareupdate --mode tonormal"
                'state_checker': self.check_devsw_off_transition,
                'userspace_action': (self.faft_client.run_shell_command,
                    'chromeos-firmwareupdate --mode tonormal'),
                'reboot_action': None,
            },
            {   # Step 5, expected normal mode boot, done
                'state_checker': (self.crossystem_checker, {
                    'devsw_boot': '0',
                    'mainfw_act': 'A',
                    'mainfw_type': 'normal',
                }),
            }
        ))
        self.run_faft_sequence()


    def wait_and_ctrl_d(self):
        time.sleep(self.FIRMWARE_SCREEN_DELAY)
        self.servo.ctrl_d()


    # The devsw off->on transition states are different based on platforms.
    # For Alex/ZGB, it is dev switch on but normal firmware boot.
    # For other platforms, it is dev switch on and developer firmware boot.
    def check_devsw_on_transition(self):
        fwid = self.faft_client.get_crossystem_value('fwid').lower()
        if fwid.startswith('alex') or fwid.startswith('zgb'):
            return self.crossystem_checker({
                    'devsw_boot': '1',
                    'mainfw_act': 'A',
                    'mainfw_type': 'normal',
                })
        else:
            return self.crossystem_checker({
                    'devsw_boot': '1',
                    'mainfw_act': 'A',
                    'mainfw_type': 'developer',
                })


    # The devsw on->off transition states are different based on platforms.
    # For Alex/ZGB, it is firmware B normal boot. Firmware A is still developer.
    # For other platforms, it is directly firmware A normal boot.
    def check_devsw_off_transition(self):
        fwid = self.faft_client.get_crossystem_value('fwid').lower()
        if fwid.startswith('alex') or fwid.startswith('zgb'):
            return self.crossystem_checker({
                    'devsw_boot': '0',
                    'mainfw_act': 'B',
                    'mainfw_type': 'normal',
                })
        else:
            return self.crossystem_checker({
                    'devsw_boot': '0',
                    'mainfw_act': 'A',
                    'mainfw_type': 'normal',
                })
