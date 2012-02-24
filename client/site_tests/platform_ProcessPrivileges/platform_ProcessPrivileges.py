# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test

class platform_ProcessPrivileges(cros_ui_test.UITest):
    version = 1

    auto_login = False

    def log_error(self, process, command, message):
        self.job.record('ERROR', None, command, message)
        self._failed.append(process)

    def check_process(self, process, user=None, do_login=False, grep_arg=None):
        """Check if the process is running as the specified user / root.

        Args:
            process: Process name to check.
            user: User process must run as; ignored if None.
            do_login: login before getting process information?
        """
        if do_login:
            self.login()
            # Wait for processes for user-session are started.
            time.sleep(10)

        # Get the process information
        # NOTE: ps command prints UID if the length of the user name does not
        # fit in the column width. So we explicitly set the column width to
        # make sure it prints the user name.
        pscmd = ('ps -o f,euser:%d,ruser:%d,suser:%d,fuser:%d,args '
                 '-C %s --no-headers')
        user_column_width = 10
        if user:
          user_column_width = len(user)
        pscmd = pscmd % tuple([user_column_width] * 4 + [process])
        if grep_arg:
            pscmd += ' | grep "%s"' % grep_arg
        ps = utils.system_output(pscmd,
                                 ignore_status=True, retain_output=True)

        pslines = ps.splitlines()

        # Fail if process is not running
        if not len(pslines):
            self.log_error(process, pscmd,
                           'Process %s is not running' % process)
            return

        # Check all instances of the process
        for psline in pslines:
            ps = psline.split()

            # Fail if not running as the specified user
            if user is not None:
                for uid in ps[1:5]:
                    if uid != user:
                        self.log_error(process, pscmd,
                            'Process %s running as %s; expected %s' %
                            (process, uid, user))
                        return

            # Check if process has super-user privileges
            else:
                # TODO(yusukes): Uncomment this once issue 2253 is resolved
                # if int(ps[0]) & 0x04:
                #    raise error.TestFail(
                #        'Process %s running with super-user flag' %
                #        process)
                if 'root' in ps:
                    self.log_error(process, pscmd,
                        'Process %s running as root' % process)
                    return


    def run_once(self):
        self._failed = []
        self.check_process('cashewd', user='cashew')
        self.check_process('chrome')
        self.check_process('cryptohomed', user='root')
        self.check_process('dbus-daemon', user='messagebus',
                           grep_arg=' --system --fork$')
        self.check_process('flimflamd', user='root')
        self.check_process('metrics_daemon', user='root')
        self.check_process('powerd')
        self.check_process('rsyslogd', user='root')
        self.check_process('udevd', user='root')
        self.check_process('wpa_supplicant', user='wpa')
        self.check_process('X', user='root')

        if len(self._failed) != 0:
            raise error.TestFail(
                'Failed processes: %s' % ','.join(self._failed))
