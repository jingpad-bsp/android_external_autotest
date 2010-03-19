# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import os
import logging

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils

class hardware_MemoryThroughput(test.test):
    version = 1
    preserve_srcdir = True

    def setup(self):
        os.chdir(self.srcdir)
        utils.system('make clean')
        utils.system('make')

    def run_once(self, num_iteration = -1, test_list = ''):
        exefile = os.path.join(self.srcdir, 'hardware_MemoryThroughput')
        cmd = '%s %d %s' % (exefile, num_iteration, test_list)
        self.results = utils.system_output(cmd, retain_output = True)

        # Resulting time in MicroSec / MegaBytes.
        # Write out memory operation performance in MegaBytes / Second.
        performance_pattern = re.compile(
            r"Action = ([a-z0-9.]+), BlockSize = (\w+), " +
            r"Method = (\w+), Time = ([0-9.]+)")
        keyval_list = performance_pattern.findall(self.results)
        keyvals = {}
        for keyval in keyval_list:
            key = ('mb_per_sec_memory_' +
                   keyval[0] + '_' + keyval[1] + '_' + keyval[2])
            keyvals[key] = 1000000.0 / float(keyval[3])
        self.write_perf_keyval(keyvals)

        # Detect if an error has occured during the tests.
        # Do this after writing out the test results so even an error occurred,
        # we still get the performance evaluation.
        error_pattern = re.compile(r"ERROR: \[(.+)\]")
        errors = error_pattern.findall(self.results)
        if len(errors) > 0:
            logging.debug(self.results)
            raise error.TestFail('malfunctioning memory detected');
