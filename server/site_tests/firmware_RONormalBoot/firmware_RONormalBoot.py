# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faft.faft_classes import FAFTSequence


class firmware_RONormalBoot(FAFTSequence):
    """
    Servo based firmware RO normal boot test.

    This test only runs on the firmware on which its firmware preamble flags
    have USE_RO_NORMAL enabled. Since we always build and pack a workable
    RW firmware in the RW firmware body section, although it is not used when
    the USE_RO_NORMAL flag is enabled.

    On runtime, the test disables the RO normal boot flag in the current
    firmware and checks its next boot result.
    """
    version = 1


    def setup(self, dev_mode=False):
        super(firmware_RONormalBoot, self).setup()
        self.backup_firmware()
        self.setup_dev_mode(dev_mode)
        self.setup_usbkey(usbkey=False)


    def cleanup(self):
        self.restore_firmware()
        super(firmware_RONormalBoot, self).cleanup()


    def run_once(self):
        flags = self.faft_client.bios.get_preamble_flags('a')
        if flags & vboot.PREAMBLE_USE_RO_NORMAL == 0:
            logging.info('The firmware USE_RO_NORMAL flag is disabled.')
            return

        self.register_faft_sequence((
            {   # Step 1, disable the RO normal boot flag
                'state_checker': (self.checkers.ro_normal_checker, 'A'),
                'userspace_action': (self.faft_client.bios.set_preamble_flags,
                                     ('a',
                                      flags ^ vboot.PREAMBLE_USE_RO_NORMAL)),
            },
            {   # Step 2, expected TwoStop boot, restore the original flags
                'state_checker': (lambda: self.checkers.ro_normal_checker('A',
                                              twostop=True)),
                'userspace_action': (self.faft_client.bios.set_preamble_flags,
                                     ('a', flags)),
            },
            {   # Step 3, done
                'state_checker': (self.checkers.ro_normal_checker, 'A'),
            },
        ))
        self.run_faft_sequence()
