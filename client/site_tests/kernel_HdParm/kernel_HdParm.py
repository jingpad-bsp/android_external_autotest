#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class kernel_HdParm(test.test):
    """
    Measure disk performance: both disk (-t) and cache (-T).
    """
    version = 1


    def run_once(self):
        result = utils.system_output('hdparm -T /dev/sda')
        match = re.search('(\d+\.\d+) MB\/sec', result)
        self.write_perf_keyval({'cache_throughput': match.groups()[0]})
        result = utils.system_output('hdparm -t /dev/sda')
        match = re.search('(\d+\.\d+) MB\/sec', result)
        self.write_perf_keyval({'disk_throughput': match.groups()[0]})
