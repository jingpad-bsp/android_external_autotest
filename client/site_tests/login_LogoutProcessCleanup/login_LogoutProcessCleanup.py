# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time, utils
from autotest_lib.client.bin import site_login, test
from autotest_lib.client.common_lib import error

class login_LogoutProcessCleanup(test.test):
    version = 1

    def __get_session_manager_pid(self):
        """Get the PID of the session manager."""

        return utils.system_output('pgrep "^session_manager$"',
            ignore_status = True)


    def __get_chronos_pids(self):
        """Get a list of all PIDs that are owned by chronos."""

        return utils.system_output('pgrep -U chronos',
            ignore_status = True).splitlines()


    def __get_stat_fields(self, pid):
        """Get a list of strings for the fields in /proc/pid/stat."""

        stat_file = open('/proc/%s/stat' % pid)
        return stat_file.read().split(' ')


    def __get_parent_pid(self, pid):
        """Get the parent PID of the given process."""

        return self.__get_stat_fields(pid)[3]


    def __is_process_dead(self, pid):
        """Check whether or not a process is dead.  Zombies are dead."""

        try:
            if self.__get_stat_fields(pid)[2] == 'Z':
                return True
        except IOError:
            # if the proc entry is gone, it's dead
            return True
        return False


    def __process_has_ancestor(self, pid, ancestor_pid):
        """Tests if the process pid has the ancestor ancestor_pid anywhere in
           the process tree."""

        ppid = pid
        while not (ppid == ancestor_pid or ppid == "0"):
            # This could fail if the process is killed while we are
            # looking up the parent.  In that case, treat it as if it
            # did not have the ancestor.
            try:
                ppid = self.__get_parent_pid(ppid)
            except IOError:
                return False
        return ppid == ancestor_pid


    def __has_chronos_processes(self, session_manager):
        """Checks if the system is running any processes owned by chronos that
           were not started by the session manager."""

        pids = self.__get_chronos_pids()
        for p in pids:
            if self.__is_process_dead(p):
                continue
            if not self.__process_has_ancestor(p, session_manager):
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
            site_login.attempt_login(self, script)

        # Start a process as chronos.  This should get killed when logging out.
        bg_job = utils.BgJob('su chronos -c "sleep 3600"')

        session_manager = self.__get_session_manager_pid()
        if session_manager == "":
            raise error.TestError('Could not find session manager pid')

        if not self.__has_chronos_processes(session_manager):
            raise error.TestFail('Expected to find processes owned by chronos '
                'that were not started by the session manager while logged in.')

        site_login.attempt_logout()

        logging.info('Logged out, searching for processes that should be dead')

        # Wait until we have a new session manager.  At that point, all
        # old processes should be dead.
        old_session_manager = session_manager
        while session_manager == "" or session_manager == old_session_manager:
            time.sleep(0.1)
            session_manager = self.__get_session_manager_pid()

        if self.__has_chronos_processes(session_manager):
            # Make sure the test job we started is dead.
            if bg_job.sp.returncode == None:
                bg_job.sp.kill()
            raise error.TestFail('Expected NOT to find processes owned by '
                'chronos that were not started by the session manager '
                'while logged out.')

        # Reset the logged in state to how we started
        if logged_in:
            site_login.attempt_login(self, script)
