# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils

class platform_MiniJailVfsNamespace(test.test):
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
        # Check that --namespace-vfs works
        cmd = (os.path.join(self.bindir,
                            'platform_MiniJailVfsNamespaceExpectFail.sh') +
               ' ' + os.path.join(self.bindir, 'platform_MiniJailVfsNamespace'))
        result = self.__run_cmd(cmd)
        success_pattern = re.compile(r"FAIL: (.+)")
        success = success_pattern.findall(result)
        if len(success) == 0:
          raise error.TestFail('Test setup failure--mount without minijail ' +
                               'was not visible:\n' + result)

        cmd = (os.path.join(self.bindir,
                            'platform_MiniJailVfsNamespaceFromInner.sh') +
               ' ' + os.path.join(self.bindir, 'platform_MiniJailVfsNamespace'))
        result = self.__run_cmd(cmd)
        success_pattern = re.compile(r"SUCCEED: (.+)")
        success = success_pattern.findall(result)
        if len(success) == 0:
          raise error.TestFail('Mount from within the minijail was visible ' +
                               'outside:\n' + result)

        cmd = (os.path.join(self.bindir,
                            'platform_MiniJailVfsNamespaceFromOuter.sh') +
               ' ' + os.path.join(self.bindir, 'platform_MiniJailVfsNamespace'))
        result = self.__run_cmd(cmd)
        success_pattern = re.compile(r"SUCCEED: (.+)")
        success = success_pattern.findall(result)
        if len(success) == 0:
          raise error.TestFail('Mount from outside the minijail was visible ' +
                               'inside:\n' + result)
