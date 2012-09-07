# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_CorruptFwSigA(FAFTSequence):
    """
    Servo based firmware signature A corruption test.
    """
    version = 1


    def setup(self, dev_mode=False):
        super(firmware_CorruptFwSigA, self).setup()
        self.backup_firmware()
        self.setup_dev_mode(dev_mode)


    def cleanup(self):
        self.restore_firmware()
        super(firmware_CorruptFwSigA, self).cleanup()


    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step 1, corrupt firmware signature A
                'state_checker': (self.crossystem_checker, {
                    'mainfw_act': 'A',
                    'tried_fwb': '0',
                }),
                'userspace_action': (self.faft_client.corrupt_firmware, 'a'),
            },
            {   # Step 2, expected firmware B boot and set fwb_tries flag
                'state_checker': (self.crossystem_checker, {
                    'mainfw_act': 'B',
                    'tried_fwb': '0',
                }),
                'userspace_action': self.faft_client.set_try_fw_b,
            },
            {   # Step 3, still expected firmware B boot and restore firmware A
                'state_checker': (self.crossystem_checker, {
                    'mainfw_act': 'B',
                    'tried_fwb': '1',
                }),
                'userspace_action': (self.faft_client.restore_firmware, 'a'),
            },
            {   # Step 4, expected firmware A boot, done
                'state_checker': (self.crossystem_checker, {
                    'mainfw_act': 'A',
                    'tried_fwb': '0',
                }),
            },
        ))
        self.run_faft_sequence()
