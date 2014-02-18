# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class hardware_Memtester(test.test):
    """
    This test uses memtester to find memory subsystem faults. Amount of memory
    to test is all of the free memory plus buffer and cache region with 30 MB
    reserved for OS use.
    """

    version = 1

    # Region in /proc/meminfo to used for testing
    USABLE_MEM = ['MemFree:', 'Buffers:', 'Cached:']

    # Size reserved for os, etc. when specified size=0
    RESERVED_SIZE = 30 * 1024

    def run_once(self, size=0, loop=10):
        """
        Executes the test and logs the output.

        @param size: size to test in KB. 0 means all available minus 30 MB
        @param loop: number of iteration to test memory
        """
        if size == 0:
            with open('/proc/meminfo', 'r') as f:
                for lines in f.readlines():
                    items = lines.split()
                    if items[0] in self.USABLE_MEM:
                        size += int(items[1])
            # minus 30 MB (arbitrary chosen) for OS use
            size -= self.RESERVED_SIZE

        if size <= 0:
            error.testFail('Size is less than zero.')

        logging.info('Memory test size: %dK', size)

        cmd = 'memtester %dK %d' % (size, loop)
        logging.info('cmd: %s', cmd)
        res = utils.run(cmd)

        with open(os.path.join(self.resultsdir, 'memtester_stdout'), 'w') as f:
            f.write(res.stdout)
