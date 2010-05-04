# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils

class platform_MiniJailPtraceDisabled(test.test):
    version = 1
    preserve_srcdir = True

    def setup(self):
        os.chdir(self.srcdir)
        utils.system('make clean')
        utils.system('make all')


    def __run_cmd(self, cmd):
        result = utils.system_output(cmd, retain_output=True,
                                     ignore_status=True)
        return result


    def run_once(self):
        # Check that --disable-tracing works
        check_cmd = os.path.join(self.bindir, 'platform_MiniJailPtraceDisabled')
        cmd = ('/sbin/minijail --disable-tracing -- ' + check_cmd)
        result = self.__run_cmd(cmd)
        succeed_pattern = re.compile(r"SUCCEED: (.+)")
        success = succeed_pattern.findall(result)
        if len(success) == 0:
          raise error.TestFail('Tracing of a child process was allowed')
