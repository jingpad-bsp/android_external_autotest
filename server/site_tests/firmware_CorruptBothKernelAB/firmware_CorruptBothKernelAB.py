# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faft.faft_classes import FAFTSequence


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


    def ensure_kernel_on_non_recovery(self, part):
        """Ensure the requested kernel part on normal/dev boot path.

        If not, it may be a test failure during step 2, try to recover to
        the requested kernel on normal/dev mode by recovering the whole OS
        and rebooting.

        @param part: the expected kernel partition number.
        """
        if not self.check_root_part_on_non_recovery(part):
            logging.info('Recover the disk OS by running chromeos-install...')
            self.run_faft_step({
                'userspace_action': (self.faft_client.system.run_shell_command,
                    'chromeos-install --yes')
            })


    def initialize(self, host, cmdline_args, dev_mode=False):
        super(firmware_CorruptBothKernelAB, self).initialize(host, cmdline_args)
        self.backup_kernel()
        self.backup_cgpt_attributes()
        self.setup_dev_mode(dev_mode)
        self.setup_usbkey(usbkey=True, host=False)
        self.setup_kernel('a')


    def cleanup(self):
        self.ensure_kernel_on_non_recovery('a')
        self.restore_cgpt_attributes()
        self.restore_kernel()
        super(firmware_CorruptBothKernelAB, self).cleanup()


    def run_once(self, dev_mode=False):
        platform = self.faft_client.system.get_platform_name()
        if platform in ('Mario', 'Alex', 'ZGB'):
            recovery_reason = vboot.RECOVERY_REASON['RW_NO_OS']
        elif platform in ('Aebl', 'Kaen'):
            recovery_reason = vboot.RECOVERY_REASON['RW_INVALID_OS']
        else:
            recovery_reason = (vboot.RECOVERY_REASON['DEP_RW_NO_DISK'],
                               vboot.RECOVERY_REASON['RW_NO_KERNEL'])

        self.register_faft_sequence((
            {   # Step 1, corrupt kernel A and B
                'state_checker': (self.check_root_part_on_non_recovery, 'a'),
                'userspace_action': (self.faft_client.kernel.corrupt_sig,
                                     (('a', 'b'),)),
                # Kernel is verified after firmware screen.
                # Should press Ctrl-D to skip the screen on dev_mode.
                'firmware_action': self.wait_fw_screen_and_ctrl_d if dev_mode
                                   else self.wait_fw_screen_and_plug_usb,
                'install_deps_after_boot': True,
            },
            {   # Step 2, expected recovery boot and restore the OS image.
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_type': 'recovery',
                    'recovery_reason': recovery_reason,
                }),
                'userspace_action': (self.faft_client.kernel.restore_sig,
                                     (('a', 'b'),)),
            },
            {   # Step 3, expected kernel A normal/dev boot
                'state_checker': (self.check_root_part_on_non_recovery, 'a'),
            },
        ))
        self.run_faft_sequence()
