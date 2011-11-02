# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_RecoveryButton(FAFTSequence):
    """
    Servo based recovery button test.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image --test"). On runtime, this test emulates
    recovery button pressed and reboots. It then triggers recovery mode by
    unplugging and plugging in the USB disk and checks success of it.
    """
    version = 1

    FIRMWARE_SCREEN_DELAY = 10
    USB_PLUG_DELAY = 2

    # Code dedicated for user manually requested recovery via recovery button.
    RECOVERY_BUTTON_REQUEST_CODE = '2'


    def ensure_normal_boot(self):
        """Ensure normal mode boot this time.

        If not, it may be a test failure during step 2, try to recover to
        normal mode by setting no recovery mode and rebooting the machine.
        """
        if self.crossystem_checker({'mainfw_type': 'recovery'}):
            self.servo.disable_recovery_mode
            self.faft_client.software_reboot()
            self.wait_for_client_offline()
            self.wait_for_client()


    def setup(self):
        super(firmware_RecoveryButton, self).setup()
        self.assert_test_image_in_usb_disk()
        self.servo.set('usb_mux_sel1', 'dut_sees_usbkey')


    def cleanup(self):
        self.ensure_normal_boot()
        super(firmware_RecoveryButton, self).cleanup()


    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step 1, press recovery button and reboot
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': 'normal',
                    'recoverysw_boot': '0',
                }),
                'userspace_action': self.servo.enable_recovery_mode,
                'firmware_action': self.wait_and_plug_usb,
                'install_deps_after_reboot': True,
            },
            {   # Step 2, expected recovery boot and release recovery button
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': 'recovery',
                    'recovery_reason' : self.RECOVERY_BUTTON_REQUEST_CODE,
                    'recoverysw_boot': '1',
                }),
                'userspace_action': self.servo.disable_recovery_mode,
            },
            {   # Step 3, expected normal boot
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': 'normal',
                    'recoverysw_boot': '0',
                }),
            },
        ))
        self.run_faft_sequence()


    def wait_and_plug_usb(self):
        """Wait for firmware warning screen and then unplug and plug the USB."""
        time.sleep(self.FIRMWARE_SCREEN_DELAY)
        self.servo.set('usb_mux_sel1', 'servo_sees_usbkey')
        time.sleep(self.USB_PLUG_DELAY)
        self.servo.set('usb_mux_sel1', 'dut_sees_usbkey')
