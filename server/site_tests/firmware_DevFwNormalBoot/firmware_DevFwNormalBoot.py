# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faft.faft_classes import FAFTSequence


class firmware_DevFwNormalBoot(FAFTSequence):
    """
    Servo based test forcing normal boot on dev firmware.

    This test is only meaningful on Alex/ZGB, which contains two different
    types of RW firmware: normal and developer firmware. It requires a USB
    disk plugged-in, which contains a Chrome OS test image (built by
    "build_image --test"). On runtime, this test sets developer firmware in
    A and then corrupts the firmware in B. It forces to do a normal boot.
    Going to recovery is expected.
    """
    version = 1

    # True if Alex/ZGB which contains two different types of firmware.
    has_different_dev_fw = False


    def corrupt_fw_b_and_disable_devsw(self):
        self.faft_client.bios.corrupt_sig('b')
        self.servo.disable_development_mode()


    def restore_fw_b_and_enable_devsw(self):
        self.faft_client.bios.restore_sig('b')
        self.servo.enable_development_mode()


    def initialize(self, host, cmdline_args):
        super(firmware_DevFwNormalBoot, self).initialize(host, cmdline_args)
        # This test is only meaningful on Alex/ZGB.
        if self.faft_client.system.get_platform_name() in ('Alex', 'ZGB'):
            self.has_different_dev_fw = True
            # This test is run on developer mode only.
            self.setup_dev_mode(dev_mode=True)
            self.setup_usbkey(usbkey=True, host=False)


    def run_once(self):
        if self.has_different_dev_fw:
            self.register_faft_sequence((
                {   # Step 1, expected dev fw on A, corrupt fw B and force
                    # normal boot.
                    'state_checker': (self.checkers.crossystem_checker, {
                        'devsw_boot': '1',
                        'mainfw_act': 'A',
                        'mainfw_type': 'developer',
                    }),
                    'userspace_action': self.corrupt_fw_b_and_disable_devsw,
                    'firmware_action': self.wait_fw_screen_and_plug_usb,
                    'install_deps_after_boot': True,
                },
                {   # Step 2, expected recovery boot, resume developer boot.
                    'state_checker': (self.checkers.crossystem_checker, {
                        'devsw_boot': '0',
                        'mainfw_type': 'recovery',
                        'recovery_reason' :
                                vboot.RECOVERY_REASON['RO_INVALID_RW'],
                    }),
                    'userspace_action': self.restore_fw_b_and_enable_devsw,
                },
                {   # Step 3, expected developer mode as before, done.
                    'state_checker': (self.checkers.crossystem_checker, {
                        'devsw_boot': '1',
                        'mainfw_act': 'A',
                        'mainfw_type': 'developer',
                    }),
                }
            ))
            self.run_faft_sequence()
        else:
            logging.info('This test does nothing on non-Alex/ZGB devices.')
