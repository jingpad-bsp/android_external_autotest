# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import ui_test

# We do this as a UITest so that we include any daemons that
# might be spawned at login, in our test results.
class security_NetworkListeners(ui_test.UITest):
    version = 1

    def load_baseline(self):
        # Figure out path to baseline file, by looking up our own path
        bpath = os.path.abspath(__file__)
        bpath = os.path.join(os.path.dirname(bpath), 'baseline')
        bfile = open(bpath)
        baseline_data = bfile.read()
        baseline_set = set([])
        for line in baseline_data.splitlines():
            if line[0] != '#': # skip comments
                baseline_set.add(line)
        bfile.close()
        return baseline_set


    def run_once(self):
        """
        Compare a list of processes, listening on TCP ports, to a
        baseline. Test fails if there are mismatches.
        """
        cmd = 'lsof -n -i -sTCP:LISTEN'
        cmd_output = utils.system_output(cmd, ignore_status=True)
        # Use the [1:] slice to discard line 0, the lsof output header.
        lsof_lines = cmd_output.splitlines()[1:]
        # Unlike ps, we don't have a format option so we have to parse
        # lines that look like this:
        # sshd 1915 root 3u IPv4 9221 0t0 TCP *:ssh (LISTEN)
        # Out of that, we just want e.g. sshd *:ssh
        observed_set = set([])
        for line in lsof_lines:
            fields = line.split()
            observed_set.add('%s %s' % (fields[0], fields[-2]))

        baseline_set = self.load_baseline()

        # If something in the observed set is not
        # covered by the baseline...
        diff = observed_set.difference(baseline_set)
        if diff:
            for daemon in diff:
                logging.error('Unexpected network listener: %s' % daemon)

        # Or, things in baseline are missing from the system:
        diff2 = baseline_set.difference(observed_set)
        if diff2:
            for daemon in diff2:
                logging.error('Missing expected network listener: %s' % daemon)

        if diff or diff2:
            raise error.TestFail('Baseline mismatch')
