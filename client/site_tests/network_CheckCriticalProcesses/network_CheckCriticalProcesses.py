# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class network_CheckCriticalProcesses(test.test):
    """
    Builds a process list (without spawning 'ps'), and validates
    that among these processes all the expected critical network
    processes are running.
    """
    version = 1
    NETWORK_CRITICAL_PROCESSES = [
            'dbus-daemon',
            'debugd',
            'metrics_daemon',
            'netfilter-queue',
            'powerd',
            'shill',
            'tlsdated',
            'udevd',
            'update_engine',
            'wpa_supplicant',
    ]

    def get_process_name(self, pid):
        """Gathers info about one process, given its PID

        @param pid string representing the process ID
        @return string process name

        """
        with open(os.path.join('/proc', pid, 'status')) as pid_status_file:
            for line in pid_status_file:
                fields = re.split('\s+',line)
                if fields[0] == 'Name:':
                    return fields[1]


    def get_process_list(self):
        """Returns the set the process names"""
        process_names = set()
        for pid in os.listdir('/proc'):
            if not pid.isdigit():
                continue

            # There can be a race where after we listdir(), a process
            # exits. In that case get_process_name will throw an IOError
            # becase /prod/NNNN won't exist.
            # In those cases, skip to the next go-round of our loop.
            try:
                process_names.add(self.get_process_name(pid))
            except IOError:
                continue

        return process_names


    def run_once(self):
        processes = self.get_process_list()
        missing_processes = [ p for p in self.NETWORK_CRITICAL_PROCESSES
                              if p not in processes ]
        if missing_processes:
            raise error.TestFail('The following processes are not running: %r.'
                                 '  This may affect network connectivity.'
                                  % missing_processes)
