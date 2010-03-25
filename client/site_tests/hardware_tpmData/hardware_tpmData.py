# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import site_tpm, test

class hardware_tpmData(test.test):
    """
    Tests for TPM data binding and sealing functionality.
    """
    version = 1
    preserve_srcdir = True

    def setup(self):
        site_tpm.build_trousers_tests(self.job.configdir, self.srcdir, 'data')

    def run_once(self):
        site_tpm.run_trousers_tests(self.bindir)
