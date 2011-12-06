# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_CorruptBothFwAB(FAFTSequence):
    """
    Servo based both firmware A and B corruption test.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image --test"). On runtime, this test corrupts
    both firmware A and B. On next reboot, the firmware verification fails
    and enters recovery mode. This test then checks the success of the
    recovery boot.
    """
    version = 1

    # Codes dedicated for RW firmware failed signature check.
    INVALID_RW_FW_CODE = '3'
    VERIFY_KEYBLOCK_FAIL_CODE = '19'


    def ensure_normal_boot(self):
        """Ensure normal boot this time.

        If not, it may be a test failure during step 2 or 3, try to recover to
        normal mode by recovering the firmware and rebooting.
        """
        if self.crossystem_checker({'mainfw_type': 'recovery'}):
            self.run_faft_step({
                'userspace_action': (self.faft_client.run_shell_command,
                    'chromeos-firmwareupdate --mode recovery')
            })


    def setup(self, dev_mode=False):
        super(firmware_CorruptBothFwAB, self).setup()
        self.assert_test_image_in_usb_disk()
        self.servo.set('usb_mux_sel1', 'dut_sees_usbkey')
        self.setup_dev_mode(dev_mode)


    def cleanup(self):
        self.ensure_normal_boot()
        super(firmware_CorruptBothFwAB, self).cleanup()


    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step 1, corrupt both firmware A and B
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': ('normal', 'developer'),
                    'recoverysw_boot': '0',
                }),
                'userspace_action': (self.faft_client.corrupt_firmware,
                                     ('a', 'b')),
                'firmware_action': self.wait_fw_screen_and_plug_usb,
                'install_deps_after_boot': True,
            },
            {   # Step 2, expected recovery boot and set fwb_tries flag
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': 'recovery',
                    'recovery_reason': (self.INVALID_RW_FW_CODE,
                                        self.VERIFY_KEYBLOCK_FAIL_CODE),
                    'recoverysw_boot': '0',
                }),
                'userspace_action': self.faft_client.set_try_fw_b,
                'firmware_action': self.wait_fw_screen_and_plug_usb,
            },
            {   # Step 3, still expected recovery boot and restore firmware
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': 'recovery',
                    'recovery_reason': (self.INVALID_RW_FW_CODE,
                                        self.VERIFY_KEYBLOCK_FAIL_CODE),
                    'recoverysw_boot': '0',
                }),
                'userspace_action': (self.faft_client.restore_firmware,
                                     ('a', 'b')),
            },
            {   # Step 4, expected normal boot, done
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': ('normal', 'developer'),
                    'recoverysw_boot': '0',
                }),
            },
        ))
        self.run_faft_sequence()
