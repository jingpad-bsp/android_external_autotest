# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

import logging
import os
import errno

"""A test verifying processes have non-executable stacks

Examines the /proc/$pid/maps file of all running processes for the
stack segment's markings. If "x" is found, it fails.
"""

class security_RuntimeExecStack(test.test):
    version = 1

    def execstack(self, maps):
        """Reads maps fd for stack markings

        Args:
            pid: a string containing the pid to be tested.

        Returns: tuple of code and maps text relevant that code.
            0: stack not executable
            1: stack executable
            2: stack perms insane
            3: stack missing
        """
        contents = ""
        for line in maps:
            line = line.strip()
            contents += line + "\n"

            if not line.endswith('[stack]'):
                continue

            perms = line.split(' ', 2)[1]

            # Stack segment is executable.
            if 'x' in perms:
                return 1, line

            # Sanity check we have stack segment perms.
            if not 'w' in perms:
                return 2, line

            # Stack segment is non-executable.
            return 0, line

        # Should be impossible: no stack segment seen.
        return 3, contents

    def run_once(self):
        failed = set([])

        for pid in os.listdir("/proc"):
            maps_path = "/proc/%s/maps" % (pid)
            # Is this a pid directory?
            if not os.path.exists(maps_path):
                continue
            # Is this a kernel thread?
            try:
                link = os.readlink("/proc/%s/exe" % (pid))
            except OSError, e:
                if e.errno == errno.ENOENT:
                    continue
            try:
                maps = open(maps_path)
                cmd = open("/proc/%s/cmdline" % (pid)).read()
            except:
                # Allow the path to vanish out from under us. If
                # we've failed for any other reason, raise the failure.
                if os.path.exists(maps_path):
                    raise
                logging.debug('ignored: pid %s vanished' % (pid))
                continue

            # Clean up cmdline for reporting.
            cmd = cmd.replace('\x00', ' ')
            exe = cmd
            if ' ' in exe:
                exe = exe[:exe.index(' ')]

            # Check the stack segment.
            stack, report = self.execstack(maps)

            # Report outcome.
            if stack == 0:
                logging.debug('ok: %s %s %s' % (pid, exe, report))
            else:
                logging.info('FAIL: %s %s %s' % (pid, cmd, report))
                failed.add(exe)

        if len(failed) != 0:
            msg = 'Bad stacks segments: %s' % (', '.join(failed))
            raise error.TestFail(msg)
