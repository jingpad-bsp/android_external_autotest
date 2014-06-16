#!/usr/bin/python

# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import errno
import fcntl
import json
import mmap
import optparse
import os
import sys
import time

class UpdateEnginePerformanceMonitor(object):
    """Performance and resource usage monitor script.

    This script is intended to run on the DUT and will start
    collecting data when started. To stop collecting data, the caller
    should write data to stdin. The script will then stop collecting
    data and will print a JSON document with the collected data on
    stdout and then exit.

    """

    def __init__(self, verbose=False):
        """Instance initializer.

        @param verbose:  if True, prints debug info stderr.

        """
        self.verbose = verbose


    def get_update_engine_pids(self):
        """Gets all processes (tasks) in the update-engine cgroup.

        @return  a list of process identifiers.

        """
        with open('/sys/fs/cgroup/cpu/update-engine/tasks') as f:
            return [int(i) for i in f.read().split()]


    def get_info_for_pid(self, pid, pids_processed):
        """Get information about a process.

        The returned information is a tuple where the first element is
        the process name and the second element is the RSS size in
        bytes. The task and its siblings (e.g. tasks belonging to the
        same process) will be set in the |pids_processed| dict.

        @param pid:            the task to get information about.

        @param pids_processed: dictionary from process identifiers to boolean.

        @return                a tuple with information.

        """
        try:
            with open('/proc/%d/stat' % pid) as f:
                fields = f.read().split()
            # According to the proc(4) man page, field 23 is the
            # number of pages in the resident set.
            comm = fields[1]
            rss = int(fields[23]) * mmap.PAGESIZE
            tasks = os.listdir('/proc/%d/task'%pid)
            # Mark all tasks belonging to the process to avoid
            # double-counting their RSS.
            for t in tasks:
                pids_processed[int(t)] = True
            return rss, comm
        except (IOError, OSError) as e:
            # It's possible that the task vanished in the window
            # between reading the 'tasks' file and when attempting to
            # read from it (ditto for iterating over the 'task'
            # directory). Handle this gracefully.
            if e.errno == errno.ENOENT:
                return 0, ''
            raise


    def do_sample(self):
        """Sampling method.

        This collects information about all the processes in the
        update-engine cgroup. The information is used to e.g. maintain
        historical peaks etc.

        """
        if self.verbose:
            sys.stderr.write('========================================\n')
        rss_total = 0
        pids = self.get_update_engine_pids()
        pids_processed = {}
        # Loop over all PIDs (tasks) in the update-engine cgroup and
        # be careful not to double-count PIDs (tasks) belonging to the
        # same process.
        for pid in pids:
            if pid not in pids_processed:
                rss, comm = self.get_info_for_pid(pid, pids_processed)
                rss_total += rss
                if self.verbose:
                    sys.stderr.write('pid %d %s -> %d KiB\n' %
                                     (pid, comm, rss/1024))
            else:
                if self.verbose:
                    sys.stderr.write('pid %d already counted\n' % pid)
        self.rss_peak = max(rss_total, self.rss_peak)
        if self.verbose:
            sys.stderr.write('Total = %d KiB\n' % (rss_total / 1024))
            sys.stderr.write('Peak  = %d KiB\n' % (self.rss_peak / 1024))


    def run(self, fd):
        """Main sampling loop.

        Periodically sample and process performance data until there
        is data to read on |fd|. When finished, will dump the recorded
        data on stdout as a JSON document.

        @param fd: the file descriptor to read from.
        """
        self.rss_peak = 0
        # Make reads from |fd| are non-blocking.
        orig_flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, orig_flags | os.O_NONBLOCK)
        while True:
            monitor.do_sample()
            time.sleep(0.1)
            try:
                # If there's no data to read, an OSError with EAGAIN
                # will be thrown and caught below. If there is data
                # read, we'll consume it...
                os.read(fd, 1024)
                # ... so we'll only get here in case there's data to
                # read. In which case bail out of the while loop.
                break
            except OSError as e:
                if e.errno != errno.EAGAIN:
                    raise
        print json.dumps({'rss_peak': self.rss_peak})


if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose', action='store_true',
                      dest='verbose', help='print debug info to stderr')
    (options, args) = parser.parse_args()

    monitor = UpdateEnginePerformanceMonitor(options.verbose)
    # Monitor until our parent process writes to stdin.
    monitor.run(sys.stdin.fileno())
