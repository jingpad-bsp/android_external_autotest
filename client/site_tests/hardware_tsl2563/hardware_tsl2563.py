# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class hardware_tsl2563(test.test):
    """
    Test the TSL2560/1/2/3 Light Sensor device.
    Failure to find the device likely indicates the kernel module is not loaded.
    Or it could mean an i2c_adapter was not found for it.  To spoof one:
        echo tsl2563 0x29 > /sys/class/i2c-adapter/i2c-0/new_device
    This will also automatically load the module.
    """
    version = 1

    preserve_srcdir = True

    def setup(self):
        os.chdir(self.srcdir)
        utils.system('make')


    def run_once(self):
        tsl_test_cmd = os.path.join(self.srcdir, "tsl2563tst")
        utils.system(tsl_test_cmd)
