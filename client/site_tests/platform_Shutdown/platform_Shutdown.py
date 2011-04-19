# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, re
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class platform_Shutdown(test.test):
    version = 1

    def _parse_shutdown_statistics(self, filename):
        statfile = open(filename, "r")
        uptime = float(statfile.readline())
        read_sectors = float(statfile.readline())
        write_sectors = float(statfile.readline())
        statfile.close()
        return (uptime, read_sectors, write_sectors)

    def run_once(self):
        try:
            prefix = "/var/log/metrics/shutdown_"
            startstats = self._parse_shutdown_statistics(prefix + "start")
            stopstats = self._parse_shutdown_statistics(prefix + "stop")
            results = {}
            results['seconds_shutdown'] = stopstats[0] - startstats[0]
            results['sectors_read_shutdown'] = stopstats[1] - startstats[1]
            results['sectors_written_shutdown'] = stopstats[2] - startstats[2]
            self.write_perf_keyval(results)
        except IOError, e:
            print e
            raise error.TestFail('Chrome OS shutdown metrics are missing')
