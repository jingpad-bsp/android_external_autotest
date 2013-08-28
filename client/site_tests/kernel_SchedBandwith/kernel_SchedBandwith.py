#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import subprocess
import time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class kernel_SchedBandwith(test.test):
    """Test kernel CFS_BANDWIDTH scheduler mechanism (/sys/fs/cgroup/...)"""
    version = 1
    # A 30 second (default) run should result in most of the time slices being
    # throttled.  Set a conservative lower bound based on having an unknown
    # system load.  Alex commonly yields numbers in the range 311..315, which
    # includes test overhead and signal latency.
    _MIN_SECS = 30

    _CG_DIR = "/sys/fs/cgroup/cpu/chrome_renderers/background"

    def _parse_cpu_stats(self):
        """Parse and return CFS bandwidth statistics.

        From kernel/Documentation/scheduler/shed-bwc.txt

        cpu.stat:
        - nr_periods: Number of enforcement intervals that have elapsed.
        - nr_throttled: Number of times the group has been throttled/limited.
        - throttled_time: The total time duration (in nanoseconds) for which entities
          of the group have been throttled.

        Returns: tuple with nr_periods, nr_throttled, throttled_time.
        """
        nr_periods = None
        nr_throttled = None
        throttled_time = None

        fd = open(os.path.join(self._CG_DIR, "cpu.stat"))

        for ln in fd.readlines():
            logging.debug(ln)
            (name, val) = ln.split()
            logging.debug("name = %s val = %s", name, val)
            if name == 'nr_periods':
                nr_periods = int(val)
            if name == 'nr_throttled':
                nr_throttled = int(val)
            if name == 'throttled_time':
                throttled_time = int(val)

        fd.close()
        return nr_periods, nr_throttled, throttled_time


    def run_once(self):

        stats = []
        if not os.path.exists(self._CG_DIR):
            raise error.TestError("Locating cgroup dir %s" % self._CG_DIR)
        quota = utils.read_one_line(os.path.join(self._CG_DIR,
                                                 "cpu.cfs_quota_us"))
        period_us = int(utils.read_one_line(os.path.join(self._CG_DIR,
                                                     "cpu.cfs_period_us")))

        # make sure its disabled
        utils.write_one_line(os.path.join(self._CG_DIR, "cpu.cfs_quota_us"), -1)

        stats.append(self._parse_cpu_stats())
        # start a cpu-hogging task and add to group
        null_fd = open("/dev/null", "w")
        self._task = subprocess.Popen(['seq', '0', '0', '0'], stdout=null_fd)
        utils.write_one_line(os.path.join(self._CG_DIR, "tasks"), self._task.pid)
        utils.write_one_line(os.path.join(self._CG_DIR, "cpu.cfs_quota_us"),
                             int(period_us)/2)
        time.sleep(self._MIN_SECS)

        stats.append(self._parse_cpu_stats())

        # return quota to initial value
        utils.write_one_line(os.path.join(self._CG_DIR, "cpu.cfs_quota_us"),
                             quota)

        periods = stats[1][0] - stats[0][0]
        actual = stats[1][1] - stats[0][1]
        logging.info("periods tested:%d periods throttled:%d", periods, actual)
 
        # make sure we throttled at least 90% of the slices
        min_throttled = self._MIN_SECS * 1e6 / period_us * 0.9
        if actual < min_throttled:
            raise error.TestFail("Unexpected throttle count of %d" % actual)

    def cleanup(self):
        super(kernel_SchedBandwith, self).cleanup()
        if hasattr(self, '_task') and self._task:
            self._task.kill()
