# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_DevTriggerRecovery(FAFTSequence):
    """
    Servo based recovery boot test triggered by pressing enter at dev screen.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image --test"). On runtime, this test changes dev
    switch and reboot. It then presses the enter key at dev warning screen to
    trigger recovery boot and checks the success of it.
    """
    version = 1

    FIRMWARE_SCREEN_DELAY = 10
    TEXT_SCREEN_DELAY = 20

    DEV_SCREEN_TO_RECOVERY_CODE = '65'

    # True if Alex/ZBG which needs a transition state to enter dev mode.
    need_dev_transition = False

    def ensure_normal_boot(self):
        """Ensure normal mode boot this time.

        If not, it may be a test failure during step 3, try to recover to
        normal mode by setting no dev switch and restoring normal firmware.
        """
        if not self.crossystem_checker({'devsw_boot': '0', 'mainfw_act': 'A',
                'mainfw_type': 'normal'}):
            self.servo.disable_development_mode()
            self.faft_client.run_shell_command(
                    'chromeos-firmwareupdate --mode tonormal')
            self.wait_for_client_offline()
            self.wait_for_client()


    def setup(self):
        super(firmware_DevTriggerRecovery, self).setup()
        self.assert_test_image_in_usb_disk()
        self.servo.set('usb_mux_sel1', 'dut_sees_usbkey')


    def cleanup(self):
        self.ensure_normal_boot()
        super(firmware_DevTriggerRecovery, self).cleanup()


    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step 1, enable dev mode
                'state_checker': (self.crossystem_checker, {
                    'devsw_boot': '0',
                    'mainfw_act': 'A',
                    'mainfw_type': 'normal',
                    'recoverysw_boot': '0',
                }),
                'userspace_action': self.servo.enable_development_mode,
                'firmware_action': self.wait_and_ctrl_d,
            },
            {   # Step 2, expected values based on platforms (see below),
                # run "chromeos-firmwareupdate --mode todev",
                # and trigger recovery boot at dev screen
                'state_checker': self.check_devsw_on_transition,
                'userspace_action': (self.faft_client.run_shell_command,
                    'chromeos-firmwareupdate --mode todev'),
                'reboot_action': None,
                'firmware_action': self.wait_and_trigger_recovery,
                'install_deps_after_reboot': True,
            },
            {   # Step 3, expected recovery boot and disable dev switch
                'state_checker': (self.crossystem_checker, {
                    'devsw_boot': '1',
                    'mainfw_type': 'recovery',
                    'recovery_reason' : self.DEV_SCREEN_TO_RECOVERY_CODE,
                    'recoverysw_boot': '0',
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
            },
        ))
        self.run_faft_sequence()


    def wait_and_ctrl_d(self):
        """Wait for firmware warning screen and press Ctrl-D."""
        time.sleep(self.FIRMWARE_SCREEN_DELAY)
        self.servo.ctrl_d()


    def wait_and_trigger_recovery(self):
        """Wait for firmware warning screen and trigger recovery boot."""
        time.sleep(self.FIRMWARE_SCREEN_DELAY)
        self.servo.enter_key()

        # For Alex/ZGB, there is a dev warning screen in text mode.
        # Skip it by pressing Ctrl-D.
        if self.need_dev_transition:
            time.sleep(self.TEXT_SCREEN_DELAY)
            self.servo.ctrl_d()


    # The devsw off->on transition states are different based on platforms.
    # For Alex/ZGB, it is dev switch on but normal firmware boot.
    # For other platforms, it is dev switch on and developer firmware boot.
    def check_devsw_on_transition(self):
        fwid = self.faft_client.get_crossystem_value('fwid').lower()
        if fwid.startswith('alex') or fwid.startswith('zgb'):
            self.need_dev_transition = True
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
        if self.need_dev_transition:
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
