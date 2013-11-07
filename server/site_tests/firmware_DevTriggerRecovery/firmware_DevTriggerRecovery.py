# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faft.faft_classes import FAFTSequence


class firmware_DevTriggerRecovery(FAFTSequence):
    """
    Servo based recovery boot test triggered by pressing enter at dev screen.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image --test"). On runtime, this test changes dev
    switch and reboot. It then presses the enter key at dev warning screen to
    trigger recovery boot and checks the success of it.
    """
    version = 1

    # True if Alex/ZGB which needs a transition state to enter dev mode.
    need_dev_transition = False


    # The devsw off->on transition states are different based on platforms.
    # For Alex/ZGB, it is dev switch on but normal firmware boot.
    # For other platforms, it is dev switch on and developer firmware boot.
    def check_devsw_on_transition(self):
        if self.faft_client.system.get_platform_name() in ('Alex', 'ZGB'):
            self.need_dev_transition = True
            return self.checkers.crossystem_checker({
                    'devsw_boot': '1',
                    'mainfw_act': 'A',
                    'mainfw_type': 'normal',
                })
        else:
            return self.checkers.crossystem_checker({
                    'devsw_boot': '1',
                    'mainfw_act': 'A',
                    'mainfw_type': 'developer',
                })


    # The devsw on->off transition states are different based on platforms.
    # For Alex/ZGB, it is firmware B normal boot. Firmware A is still developer.
    # For other platforms, it is directly firmware A normal boot.
    def check_devsw_off_transition(self):
        if self.need_dev_transition:
            return self.checkers.crossystem_checker({
                    'devsw_boot': '0',
                    'mainfw_act': 'B',
                    'mainfw_type': 'normal',
                })
        else:
            return self.checkers.crossystem_checker({
                    'devsw_boot': '0',
                    'mainfw_act': 'A',
                    'mainfw_type': 'normal',
                })


    def initialize(self, host, cmdline_args):
        super(firmware_DevTriggerRecovery, self).initialize(host, cmdline_args)
        self.setup_dev_mode(dev_mode=False)
        self.setup_usbkey(usbkey=True, host=False)


    def run_once(self):
        if self.faft_config.keyboard_dev:
            logging.info('This test is no longer valid in keyboard controlled '
                         'dev mode firmware.')
            return

        self.register_faft_sequence((
            {   # Step 1, enable dev mode
                'state_checker': (self.checkers.crossystem_checker, {
                    'devsw_boot': '0',
                    'mainfw_act': 'A',
                    'mainfw_type': 'normal',
                }),
                'userspace_action': self.servo.enable_development_mode,
                'firmware_action': self.wait_fw_screen_and_ctrl_d,
            },
            {   # Step 2, expected values based on platforms (see above),
                # run "chromeos-firmwareupdate --mode todev && reboot",
                # and trigger recovery boot at dev screen
                'state_checker': self.check_devsw_on_transition,
                'userspace_action': (self.faft_client.system.run_shell_command,
                    'chromeos-firmwareupdate --mode todev && reboot'),
                # Ignore the default reboot_action here because the
                # userspace_action (firmware updater) will reboot the system.
                'reboot_action': None,
                'firmware_action': (self.wait_fw_screen_and_trigger_recovery,
                                    self.need_dev_transition),
                'install_deps_after_boot': True,
            },
            {   # Step 3, expected recovery boot and disable dev switch
                'state_checker': (self.checkers.crossystem_checker, {
                    'devsw_boot': '1',
                    'mainfw_type': 'recovery',
                    'recovery_reason' : vboot.RECOVERY_REASON['RW_DEV_SCREEN'],
                }),
                'userspace_action': self.servo.disable_development_mode,
            },
            {   # Step 4, expected values based on platforms (see above),
                # and run "chromeos-firmwareupdate --mode tonormal && reboot"
                'state_checker': self.check_devsw_off_transition,
                'userspace_action': (self.faft_client.system.run_shell_command,
                    'chromeos-firmwareupdate --mode tonormal && reboot'),
                'reboot_action': None,
            },
            {   # Step 5, expected normal mode boot, done
                'state_checker': (self.checkers.crossystem_checker, {
                    'devsw_boot': '0',
                    'mainfw_act': 'A',
                    'mainfw_type': 'normal',
                }),
            },
        ))
        self.run_faft_sequence()
