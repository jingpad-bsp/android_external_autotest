# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.server.cros.faft.faft_classes import FAFTSequence


class firmware_SoftwareSync(FAFTSequence):
    """
    Servo based EC software sync test.
    """
    version = 1


    def setup(self, dev_mode=False):
        super(firmware_SoftwareSync, self).setup()
        self.backup_firmware()
        self.setup_dev_mode(dev_mode)
        self.setup_usbkey(usbkey=False)
        self.setup_rw_boot()
        self.dev_mode = dev_mode


    def cleanup(self):
        self.restore_firmware()
        super(firmware_SoftwareSync, self).cleanup()


    def record_hash_and_corrupt(self):
        """Record current EC hash and corrupt EC firmware."""
        self._ec_hash = self.faft_client.ec.get_firmware_sha()
        logging.info("Stored EC hash: %s", self._ec_hash)
        self.faft_client.ec.corrupt_body('rw')


    def software_sync_checker(self):
        """Check EC firmware is restored by software sync."""
        ec_hash = self.faft_client.ec.get_firmware_sha()
        logging.info("Current EC hash: %s", self._ec_hash)
        if self._ec_hash != ec_hash:
            return False
        return self.checkers.ec_act_copy_checker('RW')


    def wait_software_sync_and_boot(self):
        """Wait for software sync to update EC."""
        if self.dev_mode:
            time.sleep(self.delay.software_sync_update + self.delay.dev_screen)
            self.press_ctrl_d()
        else:
            time.sleep(self.delay.software_sync_update)


    def run_once(self):
        self.register_faft_sequence((
            {   # Step 1, Corrupt EC firmware RW body
                'state_checker': (self.checkers.ec_act_copy_checker, 'RW'),
                'userspace_action': self.record_hash_and_corrupt,
                'firmware_action': self.wait_software_sync_and_boot,
                'reboot_action': self.sync_and_ec_reboot,
            },
            {   # Step 2, expect EC in RW and RW is restored
                'state_checker': self.software_sync_checker,
                'firmware_action': self.wait_software_sync_and_boot,
            },
        ))
        self.run_faft_sequence()
