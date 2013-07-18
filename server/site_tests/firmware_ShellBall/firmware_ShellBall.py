# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.server.cros.faft_classes import FAFTSequence

class firmware_ShellBall(FAFTSequence):
    """
    chromeos-firmwareupdate functional tests.

    Checks the mode condition and enables or disables developement mode
    accordingly and runs all shellball functioanl tests.
    """
    version = 1

    _shellball_name = None

    def update_firmware(self, mode):
        self.faft_client.system.run_shell_command('%s --mode %s' %
            (self._shellball_name, mode))
        # Enalbe dev mode if the mode is todev.
        if mode == 'todev':
            self.servo.enable_development_mode()
        # Disable dev mode if the mode is tonormal.
        elif mode == 'tonormal':
            self.servo.disable_development_mode()

    def install_original_firmware(self):
        self.faft_client.system.run_shell_command(
            'sudo chromeos-firmwareupdate --mode=factory_install')
        self.invalidate_firmware_setup()

    def setup(self, host=None, shellball_path=None, shellball_name=None):
        super(firmware_ShellBall, self).setup()
        self._shellball_name = "/home/chronos/%s" % self._shellball_name
        host.send_file("%s/%s" %(shellball_path, shellball_name),
                       self._shellball_name)
        self.faft_client.system.run_shell_command('chmod +x %s' %
                                           self._shellball_name)
        self.setup_dev_mode(dev_mode=False)
        # Get crossystem fwid.
        [self._current_fwid] = (
            self.faft_client.system.run_shell_command_get_output(
                'crossystem fwid'))
        # Get BIOS version from shellball.
        [self._shellball_fwid] = self.faft_client. \
                                        system.run_shell_command_get_output(
                                            '%s -V | grep "BIOS version"' \
                                            ' | sed "s/BIOS version: ' \
                                            '\(.*\)/\\1/" '
                                            % self._shellball_name)

    def cleanup(self):
        if os.path.exists(self._shellball_name):
            os.remove(self._shellball_name)
        super(firmware_ShellBall, self).cleanup()


    def run_once(self):
        self.register_faft_sequence((
            { # Step 1, change to devmode.
                'state_checker': (self.checkers.crossystem_checker, {
                    'dev_boot_usb': '0',
                 }),
                'userspace_action': (self.update_firmware, 'todev'),
                'firmware_action': (self.wait_fw_screen_and_ctrl_d),
            },
            { # Step 2, check mainfw_type and run autoupdate.
                'state_checker': (self.checkers.crossystem_checker, {
                     'mainfw_type': 'developer'
                 }),
                'userspace_action': (self.update_firmware, 'autoupdate'),
                'firmware_action': (self.wait_fw_screen_and_ctrl_d),
            },
            { # Step 3, verify fwid and install system firmware.
                'state_checker': (self.checkers.crossystem_checker, {
                    'fwid': self._shellball_fwid
                }),
                'userspace_action': (self.install_original_firmware),
                'firmware_action': (self.wait_fw_screen_and_ctrl_d),
            },
            { # Step 4, verify the old firmware id and test factory_install.
                'state_checker': (self.checkers.crossystem_checker, {
                    'fwid': self._current_fwid
                }),
                'userspace_action': (self.update_firmware, 'factory_install'),
                'firmware_action': (self.wait_fw_screen_and_ctrl_d),
            },
            { # Step 5, verify fwid and install original firmware.
                'state_checker': (self.checkers.crossystem_checker, {
                    'fwid': self._shellball_fwid
                }),
                'userspace_action': (self.install_original_firmware),
                'firmware_action': (self.wait_fw_screen_and_ctrl_d),
            },
            { # Step 6, verify old fwid.
                'state_checker': (self.checkers.crossystem_checker, {
                    'fwid': self._current_fwid
                }),
            }
        ))
        self.run_faft_sequence()
