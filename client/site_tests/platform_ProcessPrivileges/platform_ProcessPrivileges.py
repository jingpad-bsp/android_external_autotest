# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class platform_ProcessPrivileges(test.test):
    version = 1

    def run_once(self, process='X', user=None, run_as_root=False):
        """Check if the process is running as the specified user / root.

        Args:
            process: Process name to check.
            user: User process must run as; ignored if None.
            run_as_root: Is process allowed to run as root?
        """

        # Get the process information
        pscmd = 'ps -o f,euser,ruser,suser,fuser,comm -C %s --no-headers'
        ps = utils.system_output(pscmd % process, retain_output=True)

        pslines = ps.splitlines()

        # Fail if process is not running
        if not len(pslines):
            raise error.TestFail('Process %s is not running' % process)

        # Check all instances of the process
        for psline in pslines:
            ps = psline.split()

            # Fail if not running as the specified user
            if user is not None:
                for uid in ps[1:5]:
                    if uid != user:
                        raise error.TestFail(
                            'Process %s running as %s; expected %s' %
                            (uid, user))

            # Check if process has super-user privileges
            if not run_as_root:
                if int(ps[0]) & 0x04:
                    raise error.TestFail(
                        'Process %s running with super-user flag' % process)
                if 'root' in ps:
                    raise error.TestFail(
                        'Process %s running as root' % process)
