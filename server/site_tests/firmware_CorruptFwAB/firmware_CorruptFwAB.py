# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_CorruptFwAB(FAFTSequence):
    """
    Servo based both firmware A and B corruption test.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image --test"). On runtime, this test corrupts
    both firmware A and B. On next reboot, the firmware verification fails
    and enters recovery mode. This test then checks the success of the
    recovery boot.
    """
    version = 1

    FIRMWARE_SCREEN_DELAY = 10
    USB_PLUG_DELAY = 2

    # Code dedicated for RW firmware failed signature check.
    INVALID_RW_FW_CODE = '3'


    def ensure_normal_boot(self):
        """Ensure normal boot this time.

        If not, it may be a test failure during step 2, try to recover to
        normal mode by recovering the firmware and rebooting.
        """
        if self.crossystem_checker({'mainfw_type': 'recovery'}):
            self.faft_client.run_shell_command(
                    'chromeos-firmwareupdate --mode recovery')
            self.sync_and_hw_reboot()
            self.wait_for_client_offline()
            self.wait_for_client()


    def setup(self):
        super(firmware_CorruptFwAB, self).setup()
        self.assert_test_image_in_usb_disk()
        self.servo.set('usb_mux_sel1', 'dut_sees_usbkey')


    def cleanup(self):
        self.ensure_normal_boot()
        super(firmware_CorruptFwAB, self).cleanup()


    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step 1, corrupt both firmware A and B
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': 'normal',
                    'recoverysw_boot': '0',
                }),
                'userspace_action': (self.faft_client.corrupt_firmware,
                                     ('a', 'b')),
                'firmware_action': self.wait_and_plug_usb,
                'install_deps_after_reboot': True,
            },
            {   # Step 2, expected recovery boot
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': 'recovery',
                    'recovery_reason' : self.INVALID_RW_FW_CODE,
                    'recoverysw_boot': '0',
                }),
                'userspace_action': (self.faft_client.restore_firmware,
                                     ('a', 'b')),
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
