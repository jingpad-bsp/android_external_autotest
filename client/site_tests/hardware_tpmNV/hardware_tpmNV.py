# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import site_tpm, test, utils

class hardware_tpmNV(test.test):
    """
    Tests for correctness of tpm nvram support.
    """
    version = 1
    preserve_srcdir = True

    def setup(self):
        os.chdir(self.srcdir)
        utils.system('make clean all')

    def run_once(self):
        site_tpm.run_trousers_tests(self.bindir)
