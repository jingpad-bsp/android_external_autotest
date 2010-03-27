# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time, utils
from autotest_lib.client.bin import site_login, test
from autotest_lib.client.common_lib import error

class login_LogoutProcessCleanup(test.test):
    version = 1

    def get_session_manager_pid(self):
        return utils.system_output('pgrep "^session_manager$"',
            ignore_status = True)


    # Returns a list of all PIDs owned by chronos
    def get_chronos_pids(self):
        return utils.system_output('pgrep -U chronos',
            ignore_status = True).splitlines()


    def get_stat_fields(self, pid):
        stat_file = open('/proc/%s/stat' % pid)
        return stat_file.read().split(' ')


    def get_parent_pid(self, pid):
        return self.get_stat_fields(pid)[3]


    def is_process_dead(self, pid):
        try:
            # consider zombies dead
            if self.get_stat_fields(pid)[2] == 'Z':
                return True
        except IOError:
            # if the proc entry is gone, it's dead
            return True
        return False


    # Tests if the process pid has the process ancestor_pid as an ancestor
    # anywhere in the process tree
    def process_has_ancestor(self, pid, ancestor_pid):
        ppid = pid
        while not (ppid == ancestor_pid or ppid == "0"):
            # This could fail if the process is killed while we are
            # looking up the parent.  In that case, treat it as if it
            # did not have the ancestor.
            try:
                ppid = self.get_parent_pid(ppid)
            except IOError:
                return False
        return ppid == ancestor_pid


    # Checks for processes owned by chronos, but ignores all processes
    # that have the session manager as a parent.
    def has_chronos_processes(self, session_manager):
        pids = self.get_chronos_pids()
        for p in pids:
            if self.is_process_dead(p):
                continue
            if not self.process_has_ancestor(p, session_manager):
                logging.info('found pid (%s) owned by chronos and not '
                    'started by the session manager' % p)
                return True
        return False


    def setup(self):
        site_login.setup_autox(self)


    def run_once(self, script='autox_script.json', is_control=False,
            timeout=10):
        logged_in = site_login.logged_in()

        # Require that we start the test logged in
        if not logged_in:
            if not site_login.attempt_login(self, script):
                raise error.TestError('Could not login')

        # Start a process as chronos.  This should get killed when logging out.
        bg_job = utils.BgJob('su chronos -c "sleep 3600"')

        session_manager = self.get_session_manager_pid()
        if session_manager == "":
            raise error.TestError('Could not find session manager pid')

        if not self.has_chronos_processes(session_manager):
            raise error.TestFail('Expected to find processes owned by chronos '
                'that were not started by the session manager while logged in.')

        if not site_login.attempt_logout():
            raise error.TestError('Could not logout')

        logging.info('Logged out, searching for processes that should be dead')

        # Wait until we have a new session manager.  At that point, all
        # old processes should be dead.
        old_session_manager = session_manager
        while session_manager == "" or session_manager == old_session_manager:
            time.sleep(0.1)
            session_manager = self.get_session_manager_pid()

        if self.has_chronos_processes(session_manager):
            # Make sure the test job we started is dead.
            if bg_job.sp.returncode == None:
                bg_job.sp.kill()
            raise error.TestFail('Expected NOT to find processes owned by '
                'chronos that were not started by the session manager '
                'while logged out.')

        # Reset the logged in state to how we started
        if logged_in:
            if not site_login.attempt_login(self, script):
                raise error.TestError('Could not login')
