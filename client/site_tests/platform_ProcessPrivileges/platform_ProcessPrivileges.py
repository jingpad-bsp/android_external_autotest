# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
from autotest_lib.client.bin import site_login, site_ui_test, utils
from autotest_lib.client.common_lib import error

class platform_ProcessPrivileges(site_ui_test.UITest):
    version = 1

    auto_login = False

    def run_once(self, process='X', user=None, run_as_root=False,
                 do_login=False, any=False):
        """Check if the process is running as the specified user / root.

        Args:
            process: Process name to check.
            user: User process must run as; ignored if None.
            run_as_root: Is process allowed to run as root?
            do_login: login before getting process information?
            any: Test succeeds if any of processes satisfy the conditions.
        """
        if do_login:
            self.login()
            # Wait for processes for user-session are started.
            time.sleep(10)

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

            # Assume process meets conditions until proven otherwise
            user_satisfied = True
            run_as_root_satisfied = True

            # Fail if not running as the specified user
            if user is not None:
                for uid in ps[1:5]:
                    if uid != user:
                        if any:
                            user_satisfied = False
                            break
                        raise error.TestFail(
                            'Process %s running as %s; expected %s' %
                            (process, uid, user))

            # Check if process has super-user privileges
            if not run_as_root:
                # TODO(yusukes): Uncomment this once issue 2253 is resolved
                # if int(ps[0]) & 0x04:
                #    raise error.TestFail(
                #        'Process %s running with super-user flag' %
                #        process)
                if 'root' in ps:
                    if any:
                        run_as_root_satisfied = False
                        continue
                    raise error.TestFail(
                        'Process %s running as root' % process)

            # Check if conditions are met for "any" mode.
            if any and user_satisfied and run_as_root_satisfied:
                break
        else:
            if any:
                raise error.TestFail(
                    'Conditions are not met for any process %s' % process)
