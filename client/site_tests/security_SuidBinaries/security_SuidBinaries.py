# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class security_SuidBinaries(test.test):
    version = 1

    def load_baseline(self,bltype):
        # Figure out path to baseline file, by looking up our own path
        bpath = os.path.abspath(__file__)
        bpath = os.path.join(os.path.dirname(bpath), 'baseline.%s' % bltype)
        bfile = open(bpath)
        baseline_data = bfile.read()
        baseline_set = set(baseline_data.splitlines())
        bfile.close()
        return baseline_set


    def run_once(self, baseline='suid'):
        """
        Do a find on the system for setuid binaries, compare against baseline.
        Fail if these do not match.
        """
        mask = {'suid': '4000', 'sgid': '2000'}
        cmd = ('find / -wholename /proc -prune -o '
               ' -wholename /dev -prune -o '
               ' -wholename /sys -prune -o '
               ' -wholename /home/autotest -prune -o '
               ' -wholename /usr/local -prune -o '
               ' -wholename /mnt/stateful_partition -prune -o '
               '-type f -a -perm /%s -print'
               )  % mask[baseline]
        cmd_output = utils.system_output(cmd, ignore_status=True)
        observed_set = set(cmd_output.splitlines())
        baseline_set = self.load_baseline(baseline)

        # If something in the observed set is not
        # covered by the baseline...
        diff = observed_set.difference(baseline_set)
        if len(diff) > 0:
            for filepath in diff:
                logging.error('Unexpected %s binary: %s' %
                              (baseline, filepath))

        # Or, things in baseline are missing from the system:
        diff2 = baseline_set.difference(observed_set)
        if len(diff2) > 0:
            for filepath in diff2:
                logging.error('Missing %s binary: %s' %
                              (baseline, filepath))

        if (len(diff) + len(diff2)) > 0:
            raise error.TestFail('Baseline mismatch')
