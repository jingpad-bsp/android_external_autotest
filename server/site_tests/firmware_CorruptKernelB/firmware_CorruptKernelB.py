# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros.faft.faft_classes import FAFTSequence


class firmware_CorruptKernelB(FAFTSequence):
    """
    Servo based kernel B corruption test.

    This test sets kernel B boot and then corrupts kernel B. The firmware
    verifies kernel B failed so falls back to kernel A boot. This test will
    fail if kernel verification mis-behaved.
    """
    version = 1


    def setup(self, dev_mode=False):
        super(firmware_CorruptKernelB, self).setup()
        self.setup_dev_mode(dev_mode)
        self.setup_usbkey(usbkey=False)
        self.setup_kernel('a')


    def cleanup(self):
        self.ensure_kernel_boot('a')
        super(firmware_CorruptKernelB, self).cleanup()


    def run_once(self):
        self.register_faft_sequence((
            {   # Step 1, prioritize kernel B
                'state_checker': (self.checkers.root_part_checker, 'a'),
                'userspace_action': (self.reset_and_prioritize_kernel, 'b'),
                'reboot_action': self.warm_reboot,
            },
            {   # Step 2, expected kernel B boot and corrupt kernel B
                'state_checker': (self.checkers.root_part_checker, 'b'),
                'userspace_action': (self.faft_client.kernel.corrupt_sig, 'b'),
            },
            {   # Step 3, expected kernel A boot and restore kernel B
                'state_checker': (self.checkers.root_part_checker, 'a'),
                'userspace_action': (self.faft_client.kernel.restore_sig, 'b'),
            },
            {   # Step 4, expected kernel B boot and prioritize kerenl A
                'state_checker': (self.checkers.root_part_checker, 'b'),
                'userspace_action': (self.reset_and_prioritize_kernel, 'a'),
                'reboot_action': self.warm_reboot,
            },
            {   # Step 5, expected kernel A boot
                'state_checker': (self.checkers.root_part_checker, 'a'),
            },
        ))
        self.run_faft_sequence()
