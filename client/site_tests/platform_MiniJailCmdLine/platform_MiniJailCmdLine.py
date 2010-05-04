# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils

class platform_MiniJailCmdLine(test.test):
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
        # Check that -- [cmd] works
        check_cmd = (os.path.join(self.bindir, 'platform_MiniJailCmdLine') +
              ' --echoCmdLine')
        cmd = ('/sbin/minijail -- ' + check_cmd)
        result = self.__run_cmd(cmd)
        check_pattern = re.compile(r"__CMD_LINE__\n(.+)\n__CMD_LINE__",
                                   re.MULTILINE)
        m = check_pattern.search(result);
        if m:
          if (m.group(1).strip() != check_cmd):
            raise error.TestFail('The command line did not match what was ' +
                                 'passed to minijail')
        else:
          raise error.TestFail('The command line did not match what was ' +
                               'passed to minijail')
