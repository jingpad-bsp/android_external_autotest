#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test, utils


class kernel_LowMemNotify(test.test):
    """
    Test kernel low-memory notification mechanism (/dev/chromeos-low-mem)
    """
    version = 1
    executable = 'low-mem-test'

    def setup(self):
        os.chdir(self.srcdir)
        utils.make(self.executable)

    def run_once(self):
        utils.system(self.srcdir + "/" + self.executable + " autotesting",
                     timeout=60)
