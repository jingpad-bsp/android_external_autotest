# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class security_SuidBinaries(test.test):
    version = 1

    def load_baseline(self, bltype):
        baseline_file = open(os.path.join(self.bindir, 'baseline.' + bltype))
        return set(l.strip() for l in baseline_file)


    def run_once(self, baseline='suid'):
        """
        Do a find on the system for setuid binaries, compare against baseline.
        Fail if setuid binaries are found on the system but not on the baseline.
        """
        mask = {'suid': '4000', 'sgid': '2000'}
        cmd = ('find / -wholename /proc -prune -o '
               ' -wholename /dev -prune -o '
               ' -wholename /sys -prune -o '
               ' -wholename /usr/local -prune -o '
               ' -wholename /mnt/stateful_partition -prune -o '
               '-type f -a -perm /%s -print'
               )  % mask[baseline]
        cmd_output = utils.system_output(cmd, ignore_status=True)
        observed_set = set(cmd_output.splitlines())
        baseline_set = self.load_baseline(baseline)

        # Log but not fail if we find missing binaries.
        missing = baseline_set.difference(observed_set)
        if len(missing) > 0:
            for filepath in missing:
                logging.error('Missing %s binary: %s', baseline, filepath)

        # Fail if we find new binaries.
        new = observed_set.difference(baseline_set)
        if len(new) > 0:
            message = 'New %s binaries: %s' % (baseline, ', '.join(new))
            raise error.TestFail(message)
