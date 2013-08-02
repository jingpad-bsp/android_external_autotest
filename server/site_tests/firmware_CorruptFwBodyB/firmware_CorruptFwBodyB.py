# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faft.faft_classes import FAFTSequence


class firmware_CorruptFwBodyB(FAFTSequence):
    """
    Servo based firmware body B corruption test.

    The expected behavior is different if the firmware preamble USE_RO_NORMAL
    flag is enabled. In the case USE_RO_NORMAL ON, the firmware corruption
    doesn't hurt the boot results since it boots the RO path directly and does
    not load and verify the RW firmware body. In the case USE_RO_NORMAL OFF,
    the RW firwmare B corruption will result booting the firmware A.
    """
    version = 1


    def setup(self, dev_mode=False):
        super(firmware_CorruptFwBodyB, self).setup()
        self.backup_firmware()
        self.setup_dev_mode(dev_mode)
        self.setup_usbkey(usbkey=False)


    def cleanup(self):
        self.restore_firmware()
        super(firmware_CorruptFwBodyB, self).cleanup()


    def run_once(self):
        RO_enabled = (self.faft_client.bios.get_preamble_flags('b') &
                      vboot.PREAMBLE_USE_RO_NORMAL)
        self.register_faft_sequence((
            {   # Step 1, corrupt firmware body B
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_act': 'A',
                    'tried_fwb': '0',
                }),
                'userspace_action': (self.faft_client.bios.corrupt_body,
                                     'b'),
            },
            {   # Step 2, expected firmware A boot and set try_fwb flag
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_act': 'A',
                    'tried_fwb': '0',
                }),
                'userspace_action': self.faft_client.system.set_try_fw_b,
            },
            {   # Step 3, if RO enabled, expected firmware B boot; otherwise,
                # still A boot since B is corrupted. Restore B later.
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_act': 'B' if RO_enabled else 'A',
                    'tried_fwb': '1',
                }),
                'userspace_action': (self.faft_client.bios.restore_body,
                                     'b'),
            },
            {   # Step 4, final check and done
                'state_checker': (self.checkers.crossystem_checker, {
                   'mainfw_act': 'A',
                   'tried_fwb': '0',
                }),
            },
        ))
        self.run_faft_sequence()
