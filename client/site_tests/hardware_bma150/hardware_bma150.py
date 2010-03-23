# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class hardware_bma150(test.test):
    """
    Test the BMA150 accelerometer device.
    Failure to find the device likely indicates the kernel module is not loaded.
    """
    version = 1

    preserve_srcdir = True

    def setup(self):
        os.chdir(self.srcdir)
        utils.system('make')

    def run_once(self):
        bma_test_cmd = os.path.join(self.srcdir, "bma150tst")
        utils.system(bma_test_cmd)
