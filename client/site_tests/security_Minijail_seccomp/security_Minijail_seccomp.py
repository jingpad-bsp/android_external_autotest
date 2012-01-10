# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class security_Minijail_seccomp(test.test):
    version = 1


    def setup(self):
        os.chdir(self.srcdir)
        utils.make('clean')
        utils.make()


    def run_test(self, exe, expected_ret, pretty_msg):
        cmdline = '/sbin/minijail0 -S %s/policy %s/%s' % (self.bindir,
                                                          self.bindir,
                                                          exe)
        logging.info("Command line: " + cmdline)
        ret = utils.system(cmdline, ignore_status=True)

        if ret != expected_ret:
            logging.error("ret: %d, expected: %d" % (ret, expected_ret))
            raise error.TestFail(pretty_msg)


    def run_once(self):
        case_ok = ("ok", 0, "Allowed system calls failed")
        case_fail = ("fail", 253, "Blocked system calls succeeded")

        for exe, expected_ret, pretty_msg in [case_ok, case_fail]:
            self.run_test(exe, expected_ret, pretty_msg)
