# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_SoftwareSync(FAFTSequence):
    """
    Servo based EC software sync test.
    """
    version = 1


    def ensure_rw(self):
        """Ensure firmware A is not in RO-normal mode."""
        flags = self.faft_client.get_firmware_flags('a')
        if flags & vboot.PREAMBLE_USE_RO_NORMAL:
            flags = flags ^ vboot.PREAMBLE_USE_RO_NORMAL
            self.run_faft_step({
                'userspace_action': (self.faft_client.set_firmware_flags,
                    ('a', flags))
            })


    def setup(self, dev_mode=False):
        super(firmware_SoftwareSync, self).setup()
        self.backup_firmware()
        self.setup_dev_mode(dev_mode)
        self.setup_usbkey(usbkey=False)
        self.ensure_rw()


    def cleanup(self):
        self.restore_firmware()
        super(firmware_SoftwareSync, self).cleanup()


    def record_hash_and_corrupt(self):
        self._ec_hash = self.faft_client.get_EC_firmware_sha()
        logging.info("Stored EC hash: %s", self._ec_hash)
        self.faft_client.corrupt_EC_body('rw')


    def software_sync_checker(self):
        ec_hash = self.faft_client.get_EC_firmware_sha()
        logging.info("Current EC hash: %s", self._ec_hash)
        if self._ec_hash != ec_hash:
            return False
        return self.checkers.ec_act_copy_checker('RW')


    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step 1, Corrupt EC firmware RW body
                'state_checker': (self.checkers.ec_act_copy_checker, 'RW'),
                'userspace_action': self.record_hash_and_corrupt,
                'reboot_action': self.sync_and_ec_reboot,
            },
            {   # Step 2, expect EC in RW and RW is restored
                'state_checker': self.software_sync_checker,
            },
        ))
        self.run_faft_sequence()
