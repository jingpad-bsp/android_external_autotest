#!/usr/bin/python
#
# Copyright (c) 2010 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'kdlucas@chromium.org (Kelly Lucas)'

import logging

from autotest_lib.client.bin import utils, test
from autotest_lib.client.common_lib import error


class platform_MemCheck(test.test):
    """
    Verify memory usage looks correct.
    """
    version = 1
    swap_disksize_file = '/sys/block/zram0/disksize'

    def run_once(self):
        errors = 0
        # The total memory will shrink if the system bios grabs more of the
        # reserved memory. We derived the value below by giving a small
        # cushion to allow for more system BIOS usage of ram. The memref value
        # is driven by the supported netbook model with the least amount of
        # total memory.  ARM and x86 values differ considerably.
        cpuType = utils.get_cpu_arch()
        memref = 986392
        vmemref = 102400
        if cpuType == "arm":
            memref = 700000
            vmemref = 210000

        # size reported in /sys/block/zram0/disksize is in byte
        swapref = int(utils.read_one_line(self.swap_disksize_file)) / 1024

        less_refs = ['MemTotal', 'MemFree', 'VmallocTotal']
        equal_refs = ['SwapCached']
        approx_refs = ['SwapTotal']

        ref = {'MemTotal': memref,
               'MemFree': memref / 2,
               'SwapCached': 0,
               'SwapTotal': swapref,
               'VmallocTotal': vmemref,
              }

        for k in ref:
            value = utils.read_from_meminfo(k)
            if k in less_refs:
                if value < ref[k]:
                    logging.warn('%s is %d', k, value)
                    logging.warn('%s should be at least %d', k, ref[k])
                    errors += 1
            elif k in equal_refs:
                if value != ref[k]:
                    logging.warn('%s is %d', k, value)
                    logging.warn('%s should be %d', k, ref[k])
                    errors += 1
            elif k in approx_refs:
                if value < ref[k] * 0.9 or ref[k] * 1.1 < value:
                    logging.warn('%s is %d', k, value)
                    logging.warn('%s should be within 10%% of %d', k, ref[k])
                    errors += 1

        # If self.error is not zero, there were errors.
        if errors > 0:
            raise error.TestFail('Found %d incorrect values' % errors)
