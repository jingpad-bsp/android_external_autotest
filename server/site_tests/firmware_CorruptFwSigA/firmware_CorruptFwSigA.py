# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros.faft_classes import FAFTSequence


class firmware_CorruptFwSigA(FAFTSequence):
    """
    Servo based firmware signature A corruption test.
    """
    version = 1


    def setup(self, dev_mode=False):
        super(firmware_CorruptFwSigA, self).setup()
        self.backup_firmware()
        self.setup_dev_mode(dev_mode)
        self.setup_usbkey(usbkey=False)


    def cleanup(self):
        self.restore_firmware()
        super(firmware_CorruptFwSigA, self).cleanup()


    def run_once(self):
        self.register_faft_sequence((
            {   # Step 1, corrupt firmware signature A
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_act': 'A',
                    'tried_fwb': '0',
                }),
                'userspace_action': (self.faft_client.bios.corrupt_sig, 'a'),
            },
            {   # Step 2, expected firmware B boot and set fwb_tries flag
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_act': 'B',
                    'tried_fwb': '0',
                }),
                'userspace_action': self.faft_client.system.set_try_fw_b,
            },
            {   # Step 3, still expected firmware B boot and restore firmware A
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_act': 'B',
                    'tried_fwb': '1',
                }),
                'userspace_action': (self.faft_client.bios.restore_sig, 'a'),
            },
            {   # Step 4, expected firmware A boot, done
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_act': 'A',
                    'tried_fwb': '0',
                }),
            },
        ))
        self.run_faft_sequence()
