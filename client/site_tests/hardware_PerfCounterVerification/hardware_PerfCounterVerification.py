# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

import numpy

import perf_verification
import stats_utils


class hardware_PerfCounterVerification(test.test):
    """Verify perf counters count what we think they count.

    For cycles and instructions, we expect a strong correlation between
    the number of iterations of a "noploop" program and the number of
    cycles and instructions. That is, each loop iteration should retire
    a constant number of additional instructions, and should take a
    nearly constant number of additional cycles.
    """

    version = 1
    preserve_srcdir = True

    def initialize(self, events=('cycles', 'instructions')):
        self.job.require_gcc()
        self.events = events

    def setup(self):
        os.chdir(self.srcdir)
        utils.make('clean')
        utils.make()

    def run_once(self, **kwargs):
        noploop = os.path.join(self.srcdir, 'noploop')
        self.facts = perf_verification.GatherPerfStats(
                noploop, ','.join(self.events))

    def postprocess_iteration(self):
        dt = numpy.dtype([('loops', numpy.int)] +
                         [(e, numpy.int) for e in self.events])
        arr = stats_utils.FactsToNumpyArray(self.facts, dt)
        results = {}
        for y_var in self.events:
            (slope, intercept), r2 = stats_utils.LinearRegression(
                    arr['loops'], arr[y_var])
            prefix = y_var + '_'
            results[prefix+'slope'] = slope
            results[prefix+'intercept'] = intercept
            results[prefix+'r_squared'] = r2

        self.write_perf_keyval(results)

        cpu_arch = utils.get_cpu_arch()
        if cpu_arch == 'arm':
            # ARM is observed to have a somewhat weaker correlation in cycles.
            cycles_r_squared_expectation = 0.996
        else:
            cycles_r_squared_expectation = 0.999

        if ('cycles' in self.events and
            results['cycles_r_squared'] < cycles_r_squared_expectation):
            raise error.TestFail('Poor correlation for cycles ~ loops')
        if ('instructions' in self.events and
            results['instructions_r_squared'] < 0.999999):
            raise error.TestFail('Poor correlation for instructions ~ loops')

