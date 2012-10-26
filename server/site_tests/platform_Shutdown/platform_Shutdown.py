# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import StringIO


from autotest_lib.client.common_lib import error
from autotest_lib.server import test


class platform_Shutdown(test.test):
    version = 1


    def _parse_shutdown_statistics(self, filename):
        """Returns a tuple containing uptime, read_sectors, and write_sectors.
        """
        statfile = StringIO.StringIO(self.client.run_output(
                'cat %s' % filename))
        uptime = float(statfile.readline())
        read_sectors = float(statfile.readline())
        write_sectors = float(statfile.readline())
        statfile.close()
        return uptime, read_sectors, write_sectors


    def run_once(self, host):
        self.client = host
        self.client.reboot()
        prefix = '/var/log/metrics/shutdown_'

        try:
            startstats = self._parse_shutdown_statistics(prefix + 'start')
            stopstats = self._parse_shutdown_statistics(prefix + 'stop')
        except AutotestHostRunError, e:
            logging.error(e)
            raise error.TestFail('Chrome OS shutdown metrics are missing')

        results = {}
        results['seconds_shutdown'] = stopstats[0] - startstats[0]
        results['sectors_read_shutdown'] = stopstats[1] - startstats[1]
        results['sectors_written_shutdown'] = stopstats[2] - startstats[2]
        self.write_perf_keyval(results)
