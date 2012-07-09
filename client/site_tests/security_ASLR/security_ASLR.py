# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

import logging
import os
import re

"""A test verifying Address Space Layout Randomization

Uses system calls to get important pids and then gets information about
the pids in /proc/<pid/maps.  Restarts the tested processes and reads
information about them again.  If ASLR is enabled, memory mappings should
change.
"""

class security_ASLR(test.test):
    """Runs ASLR tests

    See top document comments for more information.

    Attributes:
        version: Current version of the test.
        _INITCTL_RESTART_TIMEOUT: Time in seconds that we wait for initctl
        restart to finish.
        _INITCTL_POLL_INTERVAL: Time in seconds between checks on initctl
        status when restarting.
    """
    version = 1

    _INITCTL_RESTART_TIMEOUT = 30
    _INITCTL_POLL_INTERVAL = 1

    def get_processes_to_test(self):
        """Gets processes to test for main function

        Called by run_once to get processes for this program to test.  This
        has to be a method because it constructs process objects.

        Returns:
            A list of process objects to be tested (see below for
            definition of process class.
        """
        return [
            self.process('chrome', 'ui', 'session_manager'),
            self.process('htpdate', 'htpdate'),
            self.process('debugd', 'debugd')]

    class process:
        """Holds information about a process.

        Stores information about a process and how to restart it.

        Attributes:
            __name: String name of process.
            __initctl_name: String name initctl uses to query process.
            Defaults to None.
            __parent: String name of process's parent.  Defaults to None.
        """
        def __init__(self, name, initctl_name = None, parent = None):
            self.__name = name
            self.__initctl_name = initctl_name
            self.__parent = parent

        def get_name(self):
            return self.__name

        def get_initctl_name(self):
            return self.__initctl_name

        def get_parent(self):
            return self.__parent

    class mapping:
        """Holds information about a process's address mapping.

        Stores information about one memory mapping for a process.

        Attributes:
            __name: String name of process/memory occupying the location.
            __start: String containing memory address range start.
        """
        def __init__(self, name, start):
            self.__start = start
            self.__name = name

        def set_start(self, new_value):
            self.__start = new_value

        def get_start(self):
            return self.__start

    def get_pid_of(self, process):
        """Gets pid of process

        Used for retrieving pids of processes such as init or processes
        that may have multiple instances that need to be distinguished by
        a parent pid.

        Args:
            process: process object that we want a pid for.
        """
        name = process.get_name()
        parent = process.get_parent()
        if parent is None:
            command = 'ps -C %s -o pid --no-header' % name
            ps_results = utils.system_output(command).strip()
            return ps_results

        parent_process = self.process(parent)
        ppid = self.get_pid_of(parent_process).strip()
        get_pid_command = ('ps -C %s -o pid,ppid | grep " %s$"'
            ' | awk \'{print $1}\'') % (name, ppid)
        ps_results = utils.system_output(get_pid_command).strip()
        return ps_results

    def test_randomization(self, process):
        """Tests ASLR of a single process.

        This is the main test function for the program.  It creates two data
        structures out of useful information from /proc/<pid>/maps before
        and after restarting the process and then compares address starting
        locations of all executable, stack, and heap memory.

        Args:
            pid: a string containing the pid to be tested.

        Returns:
            A dict containing a Boolean for whether or not the test passed
            and a list of string messages about passing/failing cases.
        """
        test_result = dict([('pass', True), ('results', [])])
        name = process.get_name()
        parent = process.get_parent()
        pid1 = self.get_pid_of(process)
        attempt1 = self.map(pid1)

        self.restart(process)

        pid2 = self.get_pid_of(process)
        attempt2 = self.map(pid2)

        for key, value in attempt1.iteritems():
            match_found = (attempt2.has_key(key) and
                attempt1[key].get_start() == attempt2[key].get_start())
            if match_found:
                test_result['pass'] = False
                test_result['results'].append(
                        '[FAIL] Address for %s had deterministic value: '
                        '%s' % (key, str(attempt1[key].get_start())))
            else:
                test_result['results'].append( '[PASS] Address for %s '
                        'successfully changed.' % key)
        return test_result

    def restart(self, process):
        """Restarts a process given information about it.

        Uses a system call to initctl to restart a process and verifies
        that it restarted by pollinig its pid until it changes (signifying
        successful restart).

        Args:
            process: process object containing information about process
            to restart. See above for process class definition.

        Raises:
            error.TestFail if the process isn't restarted with
            a new pid by _INITCTL_RESTART_TIMEOUT seconds.
        """
        name = process.get_name()
        initctl_name = process.get_initctl_name()
        status_command = 'initctl status %s' % initctl_name
        initial_status = utils.system_output(status_command)
        utils.system('initctl restart %s' % initctl_name)
        utils.poll_for_condition(
            lambda: self.has_restarted(process, status_command,
                initial_status),
            exception = error.TestFail(
                'initctl failed to restart process for %s' % name),
            timeout = self._INITCTL_RESTART_TIMEOUT,
            sleep_interval = self._INITCTL_POLL_INTERVAL)

    def has_restarted(self, process, status_command, initial_status):
        """Tells if initctl service is starting and has changed pid.

        Uses initctl to view the status of a given initctl_name to check
        that it is running and has a status different from initial_status
        (meaning it has a new pid).

        Args:
            process: Process object to be restarted.  See above for process
            class definition.
            status_command: String containing the syscall that
            queries the current status.
            initial_status: String containing original output from initctl
            status called.  This is what we compare to for detection of
            change.

        Returns:
            A boolean which is true if the process is running and has a
            status which is different from initial_status.
        """
        name = process.get_name()
        initctl_name = process.get_initctl_name()
        current_status = utils.system_output(status_command)
        logging.debug('Initial status: %s' % initial_status)
        logging.debug('Current status: %s' % current_status)
        regex = r'%s start/running' % initctl_name
        is_running = re.match(regex, current_status)
        is_new_pid = initial_status != current_status
        try:
            utils.system('ps -C %s' % name)
        except:
            logging.debug('Restart done: False')
            return False
        logging.debug('Restart done: %r' % (is_running and is_new_pid))
        return (is_running and is_new_pid)

    def map(self, pid):
        """Creates data structure from table in /proc/<pid>/maps.

        Gets all data from /proc/<pid>/maps, parses each entry, and saves
        entries corresponding to executable, stack, or heap memory into
        a dictionary.

        Args:
            pid: a string containing the pid to be tested.

        Returns:
            A dict mapping names to mapping objects (see above for mapping
            definition).
        """
        memory_map = dict()
        maps_file = open("/proc/%s/maps" % pid)
        for maps_line in maps_file:
            result = self.parse_result(maps_line)
            if result is None:
                continue
            name = result['name']
            start = result['start']
            perms = result['perms']
            is_memory = name == '[heap]' or name == '[stack]'
            is_useful = re.search('x', perms) is not None or is_memory
            if not is_useful:
                continue
            if not name in memory_map:
                memory_map[name] = self.mapping(name, start)
            elif memory_map[name].get_start() < start:
                memory_map[name].set_start(start)
        return memory_map

    def parse_result(self, result):
        """Builds dictionary from columns of a line of /proc/<pid>/maps

        Uses regular expressions to determine column separations.  Puts
        column data into a dict mapping column names to their string values.

        Args:
            result: one line of /proc/<pid>/maps as a string, for any <pid>.

        Returns:
            None if the regular expression wasn't matched.  Otherwise:
            A dict of string column names mapped to their string values.
            For example:

        {'start': '9e981700000', 'end': '9e981800000', 'perms': 'rwxp',
            'something': '00000000', 'major': '00', 'minor': '00', 'inode':
            '00'}
        """
        # Build regex to parse one line of proc maps table.
        memory = '(?P<start>\w+)-(?P<end>\w+)'
        perms = '(?P<perms>(r|-)(w|-)(x|-)(s|p))'
        something = '(?P<something>\w+)'
        devices = '(?P<major>\w+):(?P<minor>\w+)'
        inode = '(?P<inode>[0-9]+)'
        name = '(?P<name>([a-zA-Z0-9/]+|\[heap\]|\[stack\]))'
        regex = r'%s +%s +%s +%s +%s +%s' % (memory, perms, something,
            devices, inode, name)
        found_match = re.match(regex, result)
        if found_match is None:
            return None
        parsed_result = found_match.groupdict()
        return parsed_result

    def run_once(self, seconds = 1):
        """Main function.

        Called when test is run.  Gets processes to test and calls test on
        them.

        Raises:
            error.TestFail if any processes' memory mapping addresses are the
            same after restarting.
        """

        processes = self.get_processes_to_test()
        aslr_enabled = True
        full_results = dict()
        for current_process in processes:
            test_results = self.test_randomization(current_process)
            full_results[current_process.get_name()] = test_results['results']
            if not test_results['pass']:
                aslr_enabled = False
        logging.debug('SUMMARY:')
        for process_name, results in full_results.iteritems():
            logging.debug('Results for %s:' % process_name)
            for result in results:
                logging.debug(result)
        if not aslr_enabled:
            raise error.TestFail('One or more processes had deterministic '
                    'memory mappings')

