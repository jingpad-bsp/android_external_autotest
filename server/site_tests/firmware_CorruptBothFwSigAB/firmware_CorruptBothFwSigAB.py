# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faft.faft_classes import FAFTSequence


class firmware_CorruptBothFwSigAB(FAFTSequence):
    """
    Servo based both firmware signature A and B corruption test.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image --test"). On runtime, this test corrupts
    both firmware signature A and B. On next reboot, the firmware verification
    fails and enters recovery mode. This test then checks the success of the
    recovery boot.
    """
    version = 1


    def setup(self, dev_mode=False):
        super(firmware_CorruptBothFwSigAB, self).setup()
        self.backup_firmware()
        self.setup_dev_mode(dev_mode)
        self.setup_usbkey(usbkey=True, host=False)


    def cleanup(self):
        self.restore_firmware()
        super(firmware_CorruptBothFwSigAB, self).cleanup()


    def run_once(self, dev_mode=False):
        self.register_faft_sequence((
            {   # Step 1, corrupt both firmware signature A and B
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_type': 'developer' if dev_mode else 'normal',
                }),
                'userspace_action': (self.faft_client.bios.corrupt_sig,
                                     (('a', 'b'),)),
                'firmware_action': None if dev_mode else
                                   self.wait_fw_screen_and_plug_usb,
                'install_deps_after_boot': True,
            },
            {   # Step 2, expected recovery boot and set fwb_tries flag
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_type': 'recovery',
                    'recovery_reason': (vboot.RECOVERY_REASON['RO_INVALID_RW'],
                            vboot.RECOVERY_REASON['RW_VERIFY_KEYBLOCK']),
                }),
                'userspace_action': self.faft_client.system.set_try_fw_b,
                'firmware_action': None if dev_mode else
                                   self.wait_fw_screen_and_plug_usb,
            },
            {   # Step 3, still expected recovery boot and restore firmware
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_type': 'recovery',
                    'recovery_reason': (vboot.RECOVERY_REASON['RO_INVALID_RW'],
                            vboot.RECOVERY_REASON['RW_VERIFY_KEYBLOCK']),
                }),
                'userspace_action': (self.faft_client.bios.restore_sig,
                                     (('a', 'b'),)),
            },
            {   # Step 4, expected normal boot, done
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_type': 'developer' if dev_mode else 'normal',
                }),
            },
        ))
        self.run_faft_sequence()
