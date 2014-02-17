# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros.faft.faft_classes import FAFTSequence

class firmware_FAFTPrepare(FAFTSequence):
    """This test prepares the device for fast FAFT tests. It sets the following:
         - GBB flags
         - Kernel B and rootfs B
    """
    version = 1

    def prepare_dut(self):
        """Prepares the DUT for FAFT."""
        self.drop_backup_gbb_flags()
        self.setup_kernel('a')

    def run_once(self):
        self.register_faft_sequence((
            {
                "userspace_action": self.prepare_dut,
            },
            {   # dummy step to force a reboot
            },
        ))
        self.run_faft_sequence()
