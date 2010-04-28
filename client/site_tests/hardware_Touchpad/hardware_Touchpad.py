# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class hardware_Touchpad(test.test):
    version = 1
    preserve_srcdir = True


    def run_once(self, restart_ui=False):

        # kill chrome
        utils.system('/sbin/initctl stop ui', ignore_status=True)

        os.chdir(self.srcdir)
        args = ''
        if restart_ui:
            args += '--exit-on-error'
        status = utils.system('./start_test.sh ' + args, ignore_status=True)

        if restart_ui:
            utils.system('/sbin/initctl start ui', ignore_status=True)

        if status:
            raise error.TestFail('Test failed.')
