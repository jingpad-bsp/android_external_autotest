# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This is a profiler class for the perf profiler in ChromeOS. It differs from
the existing perf profiler in autotset by directly substituting the options
passed to the initialize function into the "perf record" command line. It also
does not produce a perf report on the client (where there are no debug
symbols) but instead copies the perf.data file back to the server for
analysis.
"""

import os, signal, subprocess
from autotest_lib.client.bin import profiler, os_dep
from autotest_lib.client.common_lib import error


class cros_perf(profiler.profiler):
    version = 1

    def initialize(self, options='-e cycles'):
        self.options = options
        self.perf_bin = os_dep.command('perf')


    def start(self, test):
        self.logfile = os.path.join(test.profdir, 'perf.data')
        cmd = ('exec %s record -a -o %s %s' %
               (self.perf_bin, self.logfile, self.options))

        self._process = subprocess.Popen(cmd, shell=True,
                                         stderr=subprocess.STDOUT)


    def stop(self, test):
        ret_code = self._process.poll()
        if ret_code is not None:
            raise error.AutotestError('perf terminated early with return code: '
                                      '%d. Please check your logs.' % ret_code)

        self._process.send_signal(signal.SIGINT)
        self._process.wait()

