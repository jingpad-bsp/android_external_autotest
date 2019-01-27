# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import logging

from autotest_lib.server.cros.faft.fingerprint_test import FingerprintTest


class firmware_FingerprintWriteProtect(FingerprintTest):
    """
    Checks whether the HW write protect prevents the fingerprint RO firmware
    from being modified.
    """
    version = 1

    def initialize(self, host):
        # TODO(tomhughes): create dependency package that has common test files
        # and utilities
        test_dir = os.path.join(self.bindir, 'tests/')
        logging.info('test_dir: %s', test_dir)
        super(firmware_FingerprintWriteProtect, self).initialize(host, test_dir)

    def run_once(self):
        """Run the test"""
        logging.info('Running rw_no_update_ro')
        self.set_hardware_write_protect(True)
        self.run_test('rw_no_update_ro.sh',
                      self.TEST_IMAGE_DEV)

