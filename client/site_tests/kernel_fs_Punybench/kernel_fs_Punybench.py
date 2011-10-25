#!/usr/bin/python
#
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, shutil, re
from autotest_lib.client.bin import utils, test

class kernel_fs_Punybench(test.test):
    """
    Run selected puny benchmarks
    """
    version = 1
    Bin = '/usr/local/opt/punybench/bin/'

    def initialize(self):
        self.results = []
        self.job.drop_caches_between_iterations = True

    def run(self, cmd, args):
        return utils.system_output(
            os.path.join(self.Bin, cmd) + ' ' + args)

    def threadtree(self):
        result = self.run('threadtree', '-d /usr/local/_Dir -k 3')
        r1 = re.search("timer avg= \d*.\d*.*$", result)
        r2 = re.search("\d*\.\d*", r1.group())
        self.write_perf_keyval({'threadtree': r2.group() + ' secs'})

    def memcpy_test(self):
        result = self.run('memcpy_test', "")
        r1 = re.search("L1 cache.*\n.*\n.*", result)
        r2 = re.search("\d+\.\d+ MiB/s$", r1.group())
        self.write_perf_keyval({'L1cache': r2.group()})

    def run_once(self):
        self.threadtree()
        self.memcpy_test()
