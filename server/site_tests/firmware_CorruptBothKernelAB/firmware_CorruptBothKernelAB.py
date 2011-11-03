# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_CorruptBothKernelAB(FAFTSequence):
    """
    Servo based both kernel A and B corruption test.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image --test"). On runtime, this test corrupts
    both kernel A and B. On next reboot, the kernel verification fails
    and enters recovery mode. This test then checks the success of the
    recovery boot.
    """
    version = 1

    # Code dedicated for OS kernel failed signature check.
    INVALID_OS_RECOVERY_CODE = '67'  # 0x43


    def check_root_part_on_non_recovery(self, part):
        """Check the partition number of root device and on normal/dev boot.

        Returns:
            True if the root device matched and on normal/dev boot;
            otherwise, False.
        """
        return self.root_part_checker(part) and \
                self.crossystem_checker({
                    'mainfw_type': ('normal', 'developer'),
                    'recoverysw_boot': '0',
                })


    def ensure_kernel_on_non_recovery(self, part):
        """Ensure the requested kernel part on normal/dev boot path.

        If not, it may be a test failure during step 2, try to recover to
        the requested kernel on normal/dev mode by recovering the whole OS
        and rebooting.
        """
        if not self.check_root_part_on_non_recovery(part):
            logging.info('Recover the disk OS by running chromeos-install...')
            self.run_faft_step({
                'userspace_action': (self.faft_client.run_shell_command,
                    'chromeos-install --yes')
            })


    def setup(self, dev_mode=False):
        super(firmware_CorruptBothKernelAB, self).setup()
        self.assert_test_image_in_usb_disk()
        self.servo.set('usb_mux_sel1', 'dut_sees_usbkey')
        self.setup_dev_mode(dev_mode)
        self.setup_kernel('a')


    def cleanup(self):
        self.ensure_kernel_on_non_recovery('a')
        super(firmware_CorruptBothKernelAB, self).cleanup()


    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step 1, corrupt kernel A and B
                'state_checker': (self.check_root_part_on_non_recovery, 'a'),
                'userspace_action': (self.faft_client.corrupt_kernel,
                                     ('a', 'b')),
                'firmware_action': self.wait_fw_screen_and_plug_usb,
                'install_deps_after_reboot': True,
            },
            {   # Step 2, expected recovery boot
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': 'recovery',
                    'recovery_reason' : self.INVALID_OS_RECOVERY_CODE,
                    'recoverysw_boot': '0',
                }),
                'userspace_action': (self.ensure_kernel_on_non_recovery, 'a'),
            },
            {   # Step 3, expected kernel A normal/dev boot
                'state_checker': (self.check_root_part_on_non_recovery, 'a'),
            },
        ))
        self.run_faft_sequence()
