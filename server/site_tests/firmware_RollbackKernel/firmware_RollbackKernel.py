# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_RollbackKernel(FAFTSequence):
    """
    Servo based kernel rollback test.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image --test"). In normal mode, this test rollbacks
    kernel A and results kernel B boot. It then rollbacks kernel B and
    results recovery boot. In developer mode, the firmware ignores kernel
    rollback check so it remains unchanged.
    """
    version = 1


    def ensure_kernel_on_non_recovery(self, part):
        """Ensure the requested kernel part on normal/dev boot path.

        If not, it may be a test failure during step 2 or 3, try to recover to
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
        super(firmware_RollbackKernel, self).setup()
        self.assert_test_image_in_usb_disk()
        self.setup_dev_mode(dev_mode)
        self.setup_kernel('a')
        self.servo.set('usb_mux_sel1', 'dut_sees_usbkey')


    def cleanup(self):
        self.ensure_kernel_on_non_recovery('a')
        super(firmware_RollbackKernel, self).cleanup()


    def run_once(self, host=None, dev_mode=False):
        # Historical reason that the old models use a different value.
        if self.faft_client.get_platform_name() in ('Mario', 'Alex', 'ZGB'):
            recovery_reason = self.RECOVERY_REASON['RW_NO_OS']
        else:
            # TODO(waihong): Should be RW_INVALID_OS but the current vboot
            # implementation overwrites it with RW_NO_DISK.
            recovery_reason = self.RECOVERY_REASON['RW_NO_DISK']

        if dev_mode:
            faft_sequence = (
                {   # Step 1, rollbacks kernel A.
                    'state_checker':
                            (self.check_root_part_on_non_recovery, 'a'),
                    'userspace_action':
                            (self.faft_client.move_kernel_backward, 'a'),
                },
                {   # Step 2, still kernel A boot since dev_mode ignores
                    # kernel rollback check.
                    'state_checker':
                            (self.check_root_part_on_non_recovery, 'a'),
                    'userspace_action':
                            (self.faft_client.move_kernel_forward, 'a'),
                },
            )
        else:
            faft_sequence = (
                {   # Step 1, rollbacks kernel A.
                    'state_checker':
                            (self.check_root_part_on_non_recovery, 'a'),
                    'userspace_action':
                            (self.faft_client.move_kernel_backward, 'a'),
                },
                {   # Step 2, expected kernel B boot and rollbacks kernel B.
                    'state_checker':
                            (self.check_root_part_on_non_recovery, 'b'),
                    'userspace_action':
                            (self.faft_client.move_kernel_backward, 'b'),
                    'firmware_action': self.wait_fw_screen_and_plug_usb,
                    'install_deps_after_boot': True,
                },
                {   # Step 3, expected recovery boot and restores the OS image.
                    'state_checker': (self.crossystem_checker, {
                        'mainfw_type': 'recovery',
                        'recovery_reason' : recovery_reason,
                    }),
                    'userspace_action': (self.faft_client.move_kernel_forward,
                                         (('a', 'b'),)),
                },
                {   # Step 4, expected kernel A boot and done.
                    'state_checker':
                            (self.check_root_part_on_non_recovery, 'a'),
                },
            )

        self.register_faft_sequence(faft_sequence)
        self.run_faft_sequence()
