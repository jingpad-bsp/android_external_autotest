# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome

# Since we parse lsof output in several places, these centralize the
# column numbering for finding things in lsof output.  For example:
# autotest 1915 root 3u IPv4 9221 0t0 TCP *:https (LISTEN)
_LSOF_COMMAND = 0
_LSOF_PID = 1
_LSOF_USER = 2
_LSOF_FD = 3
_LSOF_TYPE = 4
_LSOF_DEVICE = 5
_LSOF_NAME = 7
# In certain cases, the size/offset column is empty, making it more
# reliable to locate the last couple columns by counting from the right.
_LSOF_SIZE_OFF = 6
_LSOF_NODE = -3
_LSOF_NAME = -2

# We log in so that we include any daemons that
# might be spawned at login in our test results.
class security_NetworkListeners(test.test):
    """Check the system against a whitelist of expected network-listeners."""
    version = 1

    def load_baseline(self):
        """Loads the baseline of expected listeners."""
        # Figure out path to baseline file, by looking up our own path
        bpath = os.path.abspath(__file__)
        bpath = os.path.join(os.path.dirname(bpath), 'baseline')
        bfile = open(bpath)
        baseline_data = bfile.read()
        baseline_set = set([])
        for line in baseline_data.splitlines():
            line = line.strip()
            if len(line) != 0 and line[0] != '#': # skip comments
                baseline_set.add(line)
        bfile.close()
        return baseline_set


    def remove_autotest_noise(self, lsof_lines):
        """
        Processes underneath 'autotest' in the process tree
        unfortunately can inherit open sockets created by
        autotest. That leads to crazy-looking test failures where
        e.g. "sed" and "bash" appear to be listening on ports
        80/443. So, this takes the output of lsof and returns a
        filtered subset of it, with autotest and telemetry stuff removed.

        @param lsof_lines: a list of lines as output by the 'lsof' util.
        """
        # Compile a set of the listening sockets to ignore.
        sockets_to_ignore = set([])
        for line in lsof_lines:
            fields = line.split()
            if (fields[_LSOF_COMMAND] == 'autotest' or
                fields[_LSOF_NAME] == '127.0.0.1:%d' %
                        utils.get_chrome_remote_debugging_port()):
                sockets_to_ignore.add(fields[_LSOF_DEVICE])

        # Now that we know which ones to ignore, iterate the output again.
        lines_to_keep = []
        for line in lsof_lines:
            fields = line.split()
            if fields[_LSOF_DEVICE] in sockets_to_ignore:
                logging.debug('Ignoring %s', line)
            else:
                lines_to_keep.append(line)
        return lines_to_keep


    def run_once(self):
        """
        Compare a list of processes, listening on TCP ports, to a
        baseline. Test fails if there are mismatches.
        """
        with chrome.Chrome():
            cmd = (r'lsof -n -i -sTCP:LISTEN | '
                   # Workaround for crosbug.com/28235 using a dynamic port #.
                   r'sed "s/\\(shill.*127.0.0.1\\):.*/\1:DYNAMIC LISTEN/g"')
            cmd_output = utils.system_output(cmd, ignore_status=True,
                                             retain_output=True)
            # Use the [1:] slice to discard line 0, the lsof output header.
            lsof_lines = cmd_output.splitlines()[1:]
            # Unlike ps, we don't have a format option so we have to parse
            # lines that look like this:
            # sshd 1915 root 3u IPv4 9221 0t0 TCP *:ssh (LISTEN)
            # Out of that, we just want e.g. sshd *:ssh
            observed_set = set([])
            for line in self.remove_autotest_noise(lsof_lines):
                fields = line.split()
                observed_set.add('%s %s' % (fields[_LSOF_COMMAND],
                                            fields[_LSOF_NAME]))

            baseline_set = self.load_baseline()

            # If something in the observed set is not
            # covered by the baseline...
            diff = observed_set.difference(baseline_set)
            if diff:
                for daemon in diff:
                    logging.error('Unexpected network listener: %s', daemon)

            # Or, things in baseline are missing from the system:
            diff2 = baseline_set.difference(observed_set)
            if diff2:
                for daemon in diff2:
                    logging.error('Missing expected network listener: %s',
                                  daemon)

            if diff or diff2:
                raise error.TestFail('Baseline mismatch')
