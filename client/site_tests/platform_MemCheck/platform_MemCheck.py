#!/usr/bin/python
#
# Copyright (c) 2010 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'kdlucas@chromium.org (Kelly Lucas)'

import logging
import os

from autotest_lib.client.bin import utils, test
from autotest_lib.client.common_lib import error


class platform_MemCheck(test.test):
    """
    Verify memory usage looks correct.
    """
    version = 1

    def run_once(self):
        errors = 0
        # The total memory will shrink if the system bios grabs more of the
        # reserved memory. We derived the value below by giving a small
        # cushion to allow for more system BIOS usage of ram. The memref value
        # is driven by the supported netbook model with the least amount of
        # total memory.
        memref = 986392
        less_refs = ['MemTotal', 'MemFree', 'VmallocTotal']
        equal_refs = ['SwapCached', 'SwapTotal']

        ref = {'MemTotal': memref,
               'MemFree': memref/2,
               'SwapCached': 0,
               'SwapTotal': 0,
               'VmallocTotal': 102400,
              }

        for k in ref:
            value = utils.read_from_meminfo(k)
            if k in less_refs:
                if value < ref[k]:
                    logging.warn('%s is %d' % (k, value))
                    logging.warn('%s should be at least %d' % (k, ref[k]))
                    errors += 1
            elif k in equal_refs:
                if value != ref[k]:
                    logging.warn('%s is %d' % (k, value))
                    logging.warn('%s should be %d' % (k, ref[k]))
                    errors += 1

        # If self.error is not zero, there were errors.
        if errors > 0:
            raise error.TestFail('Found %d incorrect values' % errors)
