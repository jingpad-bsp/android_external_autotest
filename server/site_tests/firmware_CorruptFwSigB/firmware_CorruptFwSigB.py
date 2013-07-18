# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros.faft_classes import FAFTSequence


class firmware_CorruptFwSigB(FAFTSequence):
    """
    Servo based firmware signature B corruption test.
    """
    version = 1


    def setup(self, dev_mode=False):
        super(firmware_CorruptFwSigB, self).setup()
        self.backup_firmware()
        self.setup_dev_mode(dev_mode)
        self.setup_usbkey(usbkey=False)


    def cleanup(self):
        self.restore_firmware()
        super(firmware_CorruptFwSigB, self).cleanup()


    def run_once(self):
        self.register_faft_sequence((
            {   # Step 1, expected firmware A boot and corrupt firmware
                # signature B.
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_act': 'A',
                    'tried_fwb': '0',
                }),
                'userspace_action': (self.faft_client.bios.corrupt_sig, 'b'),
            },
            {   # Step 2, expected firmware A boot and set try_fwb flag
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_act': 'A',
                    'tried_fwb': '0',
                }),
                'userspace_action': self.faft_client.system.set_try_fw_b,
            },
            {   # Step 3, expected firmware A boot and restore firmware B
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_act': 'A',
                    'tried_fwb': '1',
                }),
                'userspace_action': (self.faft_client.bios.restore_sig, 'b'),
            },
            {   # Step 4, final check and done
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_act': 'A',
                    'tried_fwb': '0',
                }),
            },
        ))
        self.run_faft_sequence()
