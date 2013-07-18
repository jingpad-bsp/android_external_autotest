# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros.faft_classes import FAFTSequence


class firmware_CorruptKernelA(FAFTSequence):
    """
    Servo based kernel A corruption test.

    This test corrupts kernel A and checks for kernel B on the next boot.
    It will fail if kernel verification mis-behaved.
    """
    version = 1


    def setup(self, dev_mode=False):
        super(firmware_CorruptKernelA, self).setup()
        self.setup_dev_mode(dev_mode)
        self.setup_usbkey(usbkey=False)
        self.setup_kernel('a')


    def cleanup(self):
        self.ensure_kernel_boot('a')
        super(firmware_CorruptKernelA, self).cleanup()


    def run_once(self):
        self.register_faft_sequence((
            {   # Step 1, corrupt kernel A
                'state_checker': (self.checkers.root_part_checker, 'a'),
                'userspace_action': (self.faft_client.kernel.corrupt_sig, 'a'),
            },
            {   # Step 2, expected kernel B boot and restore kernel A
                'state_checker': (self.checkers.root_part_checker, 'b'),
                'userspace_action': (self.faft_client.kernel.restore_sig, 'a'),
            },
            {   # Step 3, expected kernel A boot
                'state_checker': (self.checkers.root_part_checker, 'a'),
            },
        ))
        self.run_faft_sequence()
