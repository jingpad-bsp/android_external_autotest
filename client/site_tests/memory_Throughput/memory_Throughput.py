# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import os

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils

class memory_Throughput(test.test):
    version = 1

    def run_once(self, num_iteration = -1, test_list = ''):
        exefile = os.path.join(self.bindir, 'memory_Throughput')
        cmd = '%s %d %s' % (exefile, num_iteration, test_list)
        self.results = utils.system_output(cmd, retain_output = True)

        # Write out memory operation performance in MicroSecond/MegaBytes.
        performance_pattern = re.compile(
            r"Action = (\w+), MemSize = (\w+), " +
            r"Method = (\w+), Time = ([0-9.]+)")
        keyval_list = performance_pattern.findall(self.results)
        for keyval in keyval_list:
            key = keyval[0] + '_' + keyval[1] + '_' + keyval[2]
            self.write_perf_keyval({key: float(keyval[3])})

        # Detect if an error has occured during the tests.
        # Do this after writing out the test results so even an error occurred,
        # we still get the performance evaluation.
        error_pattern = re.compile(r"ERROR: \[(.+)\]")
        errors = error_pattern.findall(self.results)
        if len(errors) > 0:
            raise error.TestFail('malfunctioning memory detected');

