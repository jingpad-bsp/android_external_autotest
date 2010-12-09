# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import grp
import json
import os
import pwd
import re
import string
import time

from autotest_lib.client.bin import site_login, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import ui_test

class platform_ProcessPrivilegesComprehensive(ui_test.UITest):
    """
    Builds a process list (without spawning 'ps'), and validates
    the list against a baseline of expected processes, their priviliges,
    how many we expect to find, etc.
    """
    version = 1
    baseline = None
    strict = True

    def load_baseline(self):
        # Figure out path to baseline file, by looking up our own path
        bpath = os.path.abspath(__file__)
        bpath = os.path.join(os.path.dirname(bpath), 'baseline')
        bfile = open(bpath)
        self.baseline = json.loads(bfile.read())
        bfile.close()
        # Initialize the 'seen' counter here, makes code below easier
        for user in self.baseline.keys():
            for prog in self.baseline[user].keys():
                self.baseline[user][prog]['seen'] = 0


    def get_procentry(self, pid):
        """Gathers info about one process, given its PID"""
        pid_status_file = open(os.path.join('/proc', pid, 'status'))
        procentry = {}
        # pull Name, Uids, and Guids out of the status output
        for line in pid_status_file:
            fields = re.split('\s+',line)
            if fields[0] == 'Name:':
                procentry['name'] = fields[1]
            elif fields[0] == 'Uid:' or fields[0] == 'Gid:':
                # Add dictionary items like ruid, rgid, euid, egid, etc
                # Prefer to save uname ('root') but will save uid ('123')
                # if no uname can be found for that id.
                ug = fields[0][0].lower() # 'u' or 'g'
                for i in range(1,4):
                    try:
                        if ug == 'u':
                            fields[i] = pwd.getpwuid(int(fields[i]))[0]
                        else:
                            fields[i] = grp.getgrgid(int(fields[i]))[0]
                    except KeyError:
                        # couldn't find name. We'll save bare id# instead.
                        pass

                procentry['r%sid' % ug] = fields[1]
                procentry['e%sid' % ug] = fields[2]
                procentry['s%sid' % ug] = fields[3]

        pid_status_file.close()
        return procentry


    def procwalk(self):
        """Gathers info about every process on the system"""
        for pid in os.listdir('/proc'):
            if not pid.isdigit():
                continue

            # There can be a race where after we listdir(), a process
            # exits. In that case get_procentry will throw an IOError
            # becase /prod/NNNN won't exist.
            # In those cases, skip to the next go-round of our loop.
            try:
                procentry = self.get_procentry(pid)
            except IOError:
                continue
            procname = procentry['name']
            procuid = procentry['euid']

            # The baseline might not contain a section for this uid
            if not procuid in self.baseline:
                self.baseline[procuid] = {}

            # For processes not explicitly mentioned in the baseline,
            # our implicit rule depends on how strict we want our checking.
            # In strict mode, it is an implicit "max: 0" rule (default deny)
            # In non-strict mode, it is an implicit "min: 0" (default allow)
            if not procname in self.baseline[procuid]:
                if self.strict:
                    self.baseline[procuid][procname] = {'max': 0}
                else:
                    self.baseline[procuid][procname] = {'min': 0}

            # Initialize/increment a count of how many times we see
            # this process (e.g. we may expect a min of 4 and a max of 8
            # of some certain process, so 'seen' is not a boolean).
            if not 'seen' in self.baseline[procuid][procname]:
                self.baseline[procuid][procname]['seen'] = 0
            self.baseline[procuid][procname]['seen'] += 1


    def report(self):
        """Return a list of problems identified during procwalk"""
        problems = []
        for user in self.baseline.keys():
            for prog in self.baseline[user].keys():
                # If there's a min, we may not have met it
                # If there's a max, we may have exceeded it
                if 'min' in self.baseline[user][prog]:
                    if (self.baseline[user][prog]['seen'] <
                        self.baseline[user][prog]['min']):
                        p = ('%s (run as %s): expected at least %s processes,'
                             ' saw only %s')
                        p = p % (prog, user, self.baseline[user][prog]['min'],
                                 self.baseline[user][prog]['seen'])
                        problems.append(p)

                if 'max' in self.baseline[user][prog]:
                    if (self.baseline[user][prog]['seen'] >
                        self.baseline[user][prog]['max']):
                        p = ('%s (run as %s): expected at most %s processes,'
                             ' saw %s')
                        p = p % (prog, user, self.baseline[user][prog]['max'],
                                 self.baseline[user][prog]['seen'])
                        problems.append(p)
        problems.sort()
        return problems


    def run_once(self):
        self.load_baseline()
        self.procwalk()
        problems = self.report()

        if (len(problems) != 0):
            raise error.TestFail(
                'Process list had %s mis-matches with baseline: %s%s' %
                (len(problems), string.join(problems, '.  '),
                 '(END)'))
