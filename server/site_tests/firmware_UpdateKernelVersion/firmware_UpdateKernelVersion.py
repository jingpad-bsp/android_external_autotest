# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from autotest_lib.server.cros.faftsequence import FAFTSequence
from autotest_lib.client.common_lib import error


class firmware_UpdateKernelVersion(FAFTSequence):
    """
    This is a servod based kernel update test which should run in developer
    mode. On runtime, this test modifies the kernel version of kernel b and
    modifies cgpt to reboot with kernel b. Check kernel version after reboot,
    and then recover kernel b version to original version. Here also tries to
    reboot with kernel b after recovery. If sccuess, reboot with kernel a.
    """
    version = 1

    def check_kernel_version(self, expected_ver):
        actual_ver = self.faft_client.kernel.get_version('b')
        if actual_ver != expected_ver:
            raise error.TestFail(
                'Kernel Version should be %s, but got %s.'
                % (expected_ver, actual_ver))
        else:
            logging.info(
                'Update success, now version is %s',
                actual_ver)


    def modify_kernel_b_and_set_cgpt_priority(self, delta, target_dev):
        if delta == 1:
            self.faft_client.kernel.move_version_forward('b')
        elif delta == -1:
            self.check_kernel_version(self._update_version)
            self.faft_client.kernel.move_version_backward('b')

        if target_dev == 'a':
            self.reset_and_prioritize_kernel('a')
        else:
            self.reset_and_prioritize_kernel('b')


    def setup(self, dev_mode=True):
        super(firmware_UpdateKernelVersion, self).setup()

        self.setup_dev_mode(dev_mode)

        actual_ver = self.faft_client.kernel.get_version('b')
        logging.info('Original Kernel Version of KERN-B is %s', actual_ver)

        self._update_version = actual_ver + 1
        logging.info('KERN-B will update to version %s', self._update_version)

        self.setup_kernel('a')


    def cleanup(self):
        super(firmware_UpdateKernelVersion, self).cleanup()


    def run_once(self):
        self.register_faft_sequence((
            {   # Step 1, Update Kernel Version.
                'state_checker': (self.check_root_part_on_non_recovery, 'a'),
                'userspace_action': (
                     self.modify_kernel_b_and_set_cgpt_priority, (1, 'b')),
                'reboot_action': self.warm_reboot,
            },
            {   # Step 2, Check kernel version and rollback.
                'state_checker': (self.check_root_part_on_non_recovery, 'b'),
                'userspace_action': (
                    self.modify_kernel_b_and_set_cgpt_priority, (-1, 'b')),
                'reboot_action': self.warm_reboot,
            },
            {   # Step 3, Boot with rollback kernel and change boot priority.
                'state_checker': (self.check_root_part_on_non_recovery, 'b'),
                'userspace_action':(
                    self.modify_kernel_b_and_set_cgpt_priority, (0, 'a')),
                'reboot_action': self.warm_reboot,
            },
            {   # Step 4, Check rollback version.
                'state_checker': (self.check_root_part_on_non_recovery, 'a'),
                'userspace_action': (self.check_kernel_version,
                                     self._update_version - 1)
            }
        ))

        self.run_faft_sequence()
