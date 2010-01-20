# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import os
import logging

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils

class gpu_SanAngeles(test.test):
    version = 1
    preserve_srcdir = True

    def setup(self):
        os.chdir(self.srcdir)
        utils.system('make clean')
        utils.system('make all')

    def __try_run(self, exefile):
        cmd = os.path.join(self.srcdir, exefile)
        result = utils.run(cmd, ignore_status = True)
        if len(result.stderr) > 0:
            return -1
        pattern = re.compile(r"frame_rate = ([0-9.]+)")
        report = pattern.findall(result.stdout)
        if len(report) == 0:
            return -1
        return float(report[0])            

    def run_once(self):
        # We don't have a separate check if GL or GLES is installed on the
        # system --- just hope that one of the runs will succeed.
        frame_rate = self.__try_run('SanOGLES')
        if frame_rate <= 0:
            frame_rate = self.__try_run('SanOGL')

        if frame_rate <= 0:
            raise error.TestFail('fail to complete San Angeles Observation')

        logging.info('frame_rate = %.1f' % frame_rate)
        self.write_perf_keyval(
            {'frame_per_sec_rate_san_angeles': frame_rate})
