# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
from autotest_lib.client.bin import site_login, test, utils
from autotest_lib.client.common_lib import error

class platform_ProcessPrivileges(test.test):
    version = 1

    def setup(self):
        site_login.setup_autox(self)


    def run_once(self, process='X', user=None, run_as_root=False,
                 do_login=False):
        """Check if the process is running as the specified user / root.

        Args:
            process: Process name to check.
            user: User process must run as; ignored if None.
            run_as_root: Is process allowed to run as root?
            do_login: login before getting process information?
        """
        logged_in = site_login.logged_in()

        if do_login and not logged_in:
            # Test account information embedded into json file.
            if not site_login.attempt_login(self, 'autox_script.json'):
                raise error.TestFail('Could not login')
            # Wait for processes for user-session are started.
            time.sleep(10)

        try:
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
                                (process, uid, user))

                # Check if process has super-user privileges
                if not run_as_root:
                    # TODO(yusukes): Uncomment this once issue 2253 is resolved
                    # if int(ps[0]) & 0x04:
                    #    raise error.TestFail(
                    #        'Process %s running with super-user flag' %
                    #        process)
                    if 'root' in ps:
                        raise error.TestFail(
                            'Process %s running as root' % process)
        finally:
            # If we started logged out, log back out.
            if do_login and not logged_in:
                site_login.attempt_logout()
