# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft_classes import FAFTSequence

class firmware_ECHash(FAFTSequence):
    """
    Servo based EC hash recompute test.

    This test ensures that the AP will ask the EC to recompute the hash if
    the current hash isn't the right size/offset. Use 'ectool echash' command
    to request the hash of some other part of EC EEPROM, then warm-reboot
    the AP and use 'ectool echash' to see what hash the EC has after booting.
    AP-RW should have requested the EC recompute the hash of EC-RW.
    """
    version = 1


    def setup(self):
        super(firmware_ECHash, self).setup()
        self.backup_firmware()
        self.setup_dev_mode(dev_mode=False)
        self.setup_usbkey(usbkey=False)
        self.setup_rw_boot()


    def cleanup(self):
        self.restore_firmware()
        super(firmware_ECHash, self).cleanup()


    def get_echash(self):
        """Get the current EC hash via ectool."""
        command = 'ectool echash'
        lines = self.faft_client.system.run_shell_command_get_output(command)
        pattern = re.compile('hash:    ([0-9a-f]{64})')
        for line in lines:
            matched = pattern.match(line)
            if matched:
                return matched.group(1)
        raise error.TestError("Wrong output of 'ectool echash': \n%s" %
                              '\n'.join(lines))


    def invalidate_echash(self):
        """Invalidate the EC hash by requesting hashing some other part."""
        command = 'ectool echash recalc 0 4'
        self.faft_client.system.run_shell_command(command)


    def save_echash_and_invalidate(self):
        """Save the current EC hash and invalidate it."""
        self.original_echash = self.get_echash()
        logging.info("Original EC hash: %s", self.original_echash)
        self.invalidate_echash()
        invalid_echash = self.get_echash()
        logging.info("Invalid EC hash: %s", invalid_echash)
        if invalid_echash == self.original_echash:
            raise error.TestFail("Failed to invalidate EC hash")


    def compare_echashes(self):
        """Compare the current EC with the original one."""
        recomputed_echash = self.get_echash()
        logging.info("Recomputed EC hash: %s", recomputed_echash)
        return recomputed_echash == self.original_echash


    def run_once(self):
        if not self.check_ec_capability():
            raise error.TestNAError("Nothing needs to be tested on this device")
        self.register_faft_sequence((
            {   # Step 1, save the EC hash, invalidate it, and warm reboot.
                'userspace_action': self.save_echash_and_invalidate,
            },
            {   # Step 2, compare the recomputed EC hash with the original one.
                'state_checker': self.compare_echashes,
            }
        ))
        self.run_faft_sequence()
