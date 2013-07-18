# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faft_classes import FAFTSequence


class firmware_CorruptBothFwBodyAB(FAFTSequence):
    """
    Servo based both firmware body A and B corruption test.

    The expected behavior is different if the firmware preamble USE_RO_NORMAL
    flag is enabled. In the case USE_RO_NORMAL ON, the firmware corruption
    doesn't hurt the boot results since it boots the RO path directly and does
    not load and verify the RW firmware body. In the case USE_RO_NORMAL OFF,
    the firmware verification fails on loading RW firmware and enters recovery
    mode. In this case, it requires a USB disk plugged-in, which contains a
    Chrome OS test image (built by "build_image --test").
    """
    version = 1

    use_ro = False


    def setup(self, dev_mode=False):
        super(firmware_CorruptBothFwBodyAB, self).setup()
        self.backup_firmware()
        if (self.faft_client.bios.get_preamble_flags('a') &
                vboot.PREAMBLE_USE_RO_NORMAL):
            self.use_ro = True
            self.setup_dev_mode(dev_mode)
        else:
            self.setup_dev_mode(dev_mode)
            self.setup_usbkey(usbkey=True, host=False)


    def cleanup(self):
        self.restore_firmware()
        super(firmware_CorruptBothFwBodyAB, self).cleanup()


    def run_once(self, dev_mode=False):
        if self.use_ro:
            # USE_RO_NORMAL flag is ON. Firmware body corruption doesn't
            # hurt the booting results.
            logging.info('The firmware USE_RO_NORMAL flag is enabled.')
            self.register_faft_sequence((
                {   # Step 1, corrupt both firmware body A and B
                    'state_checker': (self.checkers.crossystem_checker, {
                        'mainfw_type': 'developer' if dev_mode else 'normal',
                    }),
                    'userspace_action': (self.faft_client.bios.corrupt_body,
                                         (('a', 'b'),)),
                },
                {   # Step 2, still expected normal/developer boot and restore
                    'state_checker': (self.checkers.crossystem_checker, {
                        'mainfw_type': 'developer' if dev_mode else 'normal',
                    }),
                    'userspace_action': (self.faft_client.bios.restore_body,
                                         (('a', 'b'),)),
                },
            ))
        else:
            self.register_faft_sequence((
                {   # Step 1, corrupt both firmware body A and B
                    'state_checker': (self.checkers.crossystem_checker, {
                        'mainfw_type': 'developer' if dev_mode else 'normal',
                    }),
                    'userspace_action': (self.faft_client.bios.corrupt_body,
                                         (('a', 'b'),)),
                    'firmware_action': None if dev_mode else
                                       self.wait_fw_screen_and_plug_usb,
                    'install_deps_after_boot': True,
                },
                {   # Step 2, expected recovery boot and restore firmware
                    'state_checker': (self.checkers.crossystem_checker, {
                        'mainfw_type': 'recovery',
                        'recovery_reason':
                            (vboot.RECOVERY_REASON['RO_INVALID_RW'],
                             vboot.RECOVERY_REASON['RW_VERIFY_BODY']),
                    }),
                    'userspace_action': (self.faft_client.bios.restore_body,
                                         (('a', 'b'),)),
                },
                {   # Step 3, expected normal boot, done
                    'state_checker': (self.checkers.crossystem_checker, {
                        'mainfw_type': 'developer' if dev_mode else 'normal',
                    }),
                },
            ))
        self.run_faft_sequence()
