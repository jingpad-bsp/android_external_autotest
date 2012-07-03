# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re
import stat
import subprocess

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class security_OpenFDs(test.test):
    version = 1

    def get_fds(self, pid):
        """
        Given a pid, return the set of open fds for that pid.
        Each open fd is represented as 'mode path' e.g.
        '0500 /dev/random'.
        """
        proc_fd_dir = os.path.join('/proc/', pid, 'fd')
        fd_perms = set([])
        for link in os.listdir(proc_fd_dir):
            link_path = os.path.join(proc_fd_dir, link)
            target = os.readlink(link_path)
            mode = stat.S_IMODE(os.lstat(link_path).st_mode)
            fd_perms.add('%s %s' % (oct(mode), target))
        return fd_perms


    def snapshot_system(self):
        """
        Dumps a systemwide snapshot of open-fd and process table
        information into the results directory, to assist with any
        triage/debug later.
        """
        subprocess.call('ps -ef > "%s/ps-ef.txt"' % self.resultsdir,
                        shell=True)
        subprocess.call('ls -l /proc/*[0-9]*/fd > "%s/proc-fd.txt"' %
                        self.resultsdir, shell=True)


    def apply_filters(self, fds, filters):
        """
        Given a set of strings ('fds'), and a list of regexes ('filters'),
        use the list of regexes as a series of exclusions to apply to the set.
        (Remove every item matching any of the filters, from the set.)

        This modifies the set in-place, and returns a list containing
        any regexes which did not match anything.
        """
        failed_filters = set()
        for filter_re in filters:
            expected_fds = set([fd_perm for fd_perm in fds
                                if re.match(filter_re, fd_perm)])
            if not expected_fds:
                failed_filters.add(filter_re)
            fds -= expected_fds
        return failed_filters


    def find_pids(self, process, arg_regex):
        """
        Find all pids for a given process name whose command line
        arguments match the specified arg_regex. Returns a list of pids.
        """
        p1 = subprocess.Popen(['ps', '-C', process, '-o', 'pid,command'],
                              stdout=subprocess.PIPE)
        # We're adding '--ignored= --type=renderer' to the GPU process cmdline
        # to fix http://code.google.com/p/chromium/issues/detail?id=129884.
        # This process has different characteristics, so we need to avoid
        # finding it when we find --type=renderer tests processes.
        p2 = subprocess.Popen(['grep', '-v', '--',
                               '--ignored=.*%s' % arg_regex],
                              stdin=p1.stdout, stdout=subprocess.PIPE)
        p3 = subprocess.Popen(['grep', arg_regex], stdin=p2.stdout,
                              stdout=subprocess.PIPE)
        p4 = subprocess.Popen(['awk', '{print $1}'], stdin=p3.stdout,
                              stdout=subprocess.PIPE)
        output = p4.communicate()[0]
        return output.splitlines()


    def check_process(self, process, args, filters):
        """
        Perform a complete check for a given process/args:
        * Identify all instances (pids) of that process
        * Identify all fds open by those pids
        * Report any fds not accounted-for by the specified filter list
        * Report any filters which fail to match any open fds.
        If there were any un-accounted-for fds, or failed filters,
        mark the test failed. Returns True if test passed, False otherwise.
        """
        logging.debug('Checking %s %s' % (process, args))
        test_pass = True
        for pid in self.find_pids(process, args):
            logging.debug('Found pid %s for %s' % (pid, process))
            fds = self.get_fds(pid)
            failed_filters = self.apply_filters(fds, filters)
            if failed_filters:
                logging.error('Some filter(s) failed to match any fds: %s' %
                              repr(failed_filters))
                test_pass = False
            if fds:
                logging.error('Found unexpected fds in %s %s: %s' %
                              (process, args, repr(fds)))
                test_pass = False
        return test_pass


    def run_once(self):
        """
        Check a number of important processes on Chrome OS for
        unexpected open file descriptors. Will raise a TestFail
        exception in the event of a failure.
        """
        self.snapshot_system()
        passes = []
        filters = [r'0700 anon_inode:\[eventpoll\]',
                   r'0[35]00 pipe:.*',
                   r'0[57]00 socket:.*',
                   r'0500 /dev/null',
                   r'0[57]00 /dev/urandom',
                   r'0300 /var/log/chrome/chrome_.*',
                   r'0[37]00 /var/log/ui/ui.*',
                  ]
        passes.append(self.check_process('chrome', 'type=plugin', filters))

        filters.extend([r'0700 /dev/shm/.com.google.Chrome.*',
                        r'0500 /opt/google/chrome/chrome.pak',
                        r'0500 /opt/google/chrome/locales/en-US.pak',
                        r'0500 /opt/google/chrome/theme_resources_standard.pak',
                        r'0500 /opt/google/chrome/ui_resources_.*.pak',
                       ])
        passes.append(self.check_process('chrome', 'type=renderer', filters))

        if False in passes:
            raise error.TestFail("Unexpected changes to open fds.")
