# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faft_classes import FAFTSequence


class firmware_RecoveryButton(FAFTSequence):
    """
    Servo based recovery button test.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image --test"). On runtime, this test emulates
    recovery button pressed and reboots. It then triggers recovery mode by
    unplugging and plugging in the USB disk and checks success of it.
    """
    version = 1


    def ensure_normal_boot(self):
        """Ensure normal mode boot this time.

        If not, it may be a test failure during step 2, try to recover to
        normal mode by setting no recovery mode and rebooting the machine.
        """
        if not self.checkers.crossystem_checker(
                {'mainfw_type': ('normal', 'developer')}):
            self.run_faft_step({
                'userspace_action': self.servo.disable_recovery_mode,
            })


    def setup(self, dev_mode=False, ec_wp=None):
        super(firmware_RecoveryButton, self).setup(ec_wp=ec_wp)
        self.setup_dev_mode(dev_mode)
        self.setup_usbkey(usbkey=True, host=False)


    def cleanup(self):
        self.ensure_normal_boot()
        super(firmware_RecoveryButton, self).cleanup()


    def run_once(self, dev_mode=False):
        # The old models need users to remove and insert USB stick during boot.
        remove_usb = (self.faft_client.system.get_platform_name() in
                      ('Mario', 'Alex', 'ZGB', 'Aebl', 'Kaen'))
        self.register_faft_sequence((
            {   # Step 1, switch to recovery mode and reboot
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_type': 'developer' if dev_mode else 'normal',
                }),
                'userspace_action': self.enable_rec_mode_and_reboot,
                'reboot_action': None,
                # In the keyboard controlled recovery mode design, it doesn't
                # require users to remove and insert the USB.
                #
                # In the old design, it checks:
                #   if dev_mode ON, directly boot to USB stick if presented;
                #   if dev_mode OFF,
                #     the old models need users to remove and insert the USB;
                #     the new models directly boot to the USB.
                'firmware_action': None if self.client_attr.keyboard_dev or
                                   dev_mode or not remove_usb else
                                   self.wait_fw_screen_and_plug_usb,
                'install_deps_after_boot': True,
            },
            {   # Step 2, expected recovery boot and reboot
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_type': 'recovery',
                    'recovery_reason' : vboot.RECOVERY_REASON['RO_MANUAL'],
                }),
            },
            {   # Step 3, expected normal boot
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_type': 'developer' if dev_mode else 'normal',
                }),
            },
        ))
        self.run_faft_sequence()
