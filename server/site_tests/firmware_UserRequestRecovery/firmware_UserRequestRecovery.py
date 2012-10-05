# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_UserRequestRecovery(FAFTSequence):
    """
    Servo based user request recovery boot test.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image --test"). On runtime, this test first requests
    a recovery mode on next boot by setting the crossystem recovery_request
    flag. It then triggers recovery mode by unplugging and plugging in the USB
    disk and checks success of it.
    """
    version = 1


    def ensure_normal_boot(self):
        """Ensure normal mode boot this time.

        If not, it may be a test failure during step 2, try to recover to
        normal mode by simply rebooting the machine.
        """
        if not self.crossystem_checker(
                {'mainfw_type': ('normal', 'developer')}):
            self.run_faft_step({})


    def setup(self, dev_mode=False):
        super(firmware_UserRequestRecovery, self).setup()
        self.assert_test_image_in_usb_disk()
        self.setup_dev_mode(dev_mode)
        self.servo.enable_usb_hub(host=True)


    def cleanup(self):
        self.ensure_normal_boot()
        super(firmware_UserRequestRecovery, self).cleanup()


    def try_dev_switching_and_plug_usb(self, dev_mode):
        """Try pressing Ctrl-D and enter to check its firmware behavior."""
        # Pressing Ctrl-D + Enter / Enter + Enter should not trigger
        # dev / normal mode switching.
        if self.client_attr.keyboard_dev:
            self.wait_fw_screen_and_switch_keyboard_dev_mode(not dev_mode)
            if not dev_mode:
                self.wait_fw_screen_and_ctrl_d()

        self.wait_fw_screen_and_plug_usb()


    def run_once(self, host=None, dev_mode=False):
        self.register_faft_sequence((
            {   # Step 1, request recovery boot
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': 'developer' if dev_mode else 'normal',
                }),
                'userspace_action': self.faft_client.request_recovery_boot,
                'firmware_action': (self.try_dev_switching_and_plug_usb,
                                    dev_mode),
                'install_deps_after_boot': True,
            },
            {   # Step 2, expected recovery boot, request recovery again
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': 'recovery',
                    'recovery_reason' : vboot.RECOVERY_REASON['US_TEST'],
                }),
                'userspace_action': self.faft_client.request_recovery_boot,
                'firmware_action': None if dev_mode else
                                   self.wait_fw_screen_and_plug_usb,
            },
            {   # Step 3, expected recovery boot
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': 'recovery',
                    'recovery_reason' : vboot.RECOVERY_REASON['US_TEST'],
                }),
            },
            {   # Step 4, expected normal boot
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': 'developer' if dev_mode else 'normal',
                }),
            },
        ))
        self.run_faft_sequence()
