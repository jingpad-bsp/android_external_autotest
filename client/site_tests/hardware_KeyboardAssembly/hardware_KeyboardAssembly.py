# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class hardware_KeyboardAssembly(test.test):
    version = 1
    preserve_srcdir = True


    def run_once(self):

        # kill chrome
        utils.system('/sbin/initctl stop ui', ignore_status=True)

        os.chdir(self.srcdir)
        utils.system('./start_test.sh')
