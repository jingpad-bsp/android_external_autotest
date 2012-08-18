#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class kernel_SchedBandwith(test.test):
    """
    Test kernel CFS_BANDWIDTH scheduler mechanism (/tmp/cgroup/...)
    """
    version = 1
    executable = "cfs-bandwidth-test"
    # This is the largest absolute difference we consider acceptable
    # between the number of periods in which there was the opportunity
    # to throttle vs. the number of periods in which throttling occurred.
    # Typical results on Alex are within 0..2.
    MAX_DELTA = 3
    # A 30 second (default) run should result in most of the 300 time
    # slices being throttled.  Set a conservative lower bound based on
    # having an unknown system load.  Alex commonly yields numbers in
    # the range 311..315, which includes test overhead and signal latency.
    MIN_THROTTLED = 250

    def setup(self):
        os.chdir(self.srcdir)
        utils.make(self.executable)

    def run_once(self):
    # The default in the C code is for this to take 30 seconds + 2
    # seconds + latency.
        out = utils.run(os.path.join(self.srcdir, self.executable))
        result = out.stdout.rstrip("\r\n").split(" ")
        actual = int(result[1])
        delta = abs(int(result[0]) - actual)
        if delta > self.MAX_DELTA:
            raise error.TestFail("Test variance %d too large" % delta)
        if actual < self.MIN_THROTTLED:
            raise error.TestFail("Unexpected throttle count of %d" % actual)
