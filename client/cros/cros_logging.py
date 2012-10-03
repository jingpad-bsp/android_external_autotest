# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, time

import common
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from constants import CLEANUP_LOGS_PAUSED_FILE


def extract_kernel_timestamp(msg):
    """Extract a timestmap that appears in kernel log messages and looks
    like this:
    ... kernel: [78791.721832] ...

    Returns:
        The timestamp as float in seconds since last boot.
    """

    match = re.search(' \[\s*([0-9]+\.[0-9]+)\] ', msg)
    if match:
        return float(match.group(1))
    raise error.TestError('Could not extract timestamp from message: ' + msg)


class LogReader(object):
    """
    A class to read system log files.
    """

    def __init__(self, filename='/var/log/messages', include_rotated_logs=True):
        self._start_line = 1
        self._filename = filename
        self._include_rotated_logs = include_rotated_logs
        if not os.path.exists(CLEANUP_LOGS_PAUSED_FILE):
            raise error.TestError('LogReader created without ' +
                                  CLEANUP_LOGS_PAUSED_FILE)


    def read_all_logs(self, start=0):
        """Read all content from log files.

        Generator function.
        Return an iterator on the content of files.
        """
        log_files = []
        line_number = 1
        if self._include_rotated_logs:
            log_files.extend(utils.system_output(
                'ls -tr1 %s.*' % self._filename,
                ignore_status=True).splitlines())
        log_files.append(self._filename)
        for log_file in log_files:
            f = open(log_file)
            for line in f:
                if line_number >= start:
                    yield line
                line_number += 1
            f.close()


    def set_start_by_regexp(self, index, regexp):
        """Set the start of logs based on a regular expression.

        @param index: line matching regexp to start at, earliest log at 0.
                Negative numbers indicate matches since end of log.
        """
        regexp_compiled = re.compile(regexp)
        starts = []
        line_number = 1
        for line in self.read_all_logs():
            if regexp_compiled.match(line):
                starts.append(line_number)
            line_number += 1
        if index < -len(starts):
            self._start_line = 1
        elif index >= len(starts):
            self._start_line = line_number
        else:
            self._start_line = starts[index]


    def set_start_by_reboot(self, index):
        """ Set the start of logs (must be system log) based on reboot.

        @param index: reboot to start at, earliest log at 0.  Negative
                numbers indicate reboots since end of log.
        """
        return self.set_start_by_regexp(index,
                                        r'.*000\] Linux version \d')


    def set_start_by_current(self, relative=0):
        """ Set start of logs based on current last line.

        @param relative: line relative to current to start at.  1 means
                to start the log after this line.
        """
        count = self._start_line + relative
        for line in self.read_all_logs(start=self._start_line):
            count += 1
        self._start_line = count


    def get_logs(self):
        """ Get logs since the start line.

        Start line is set by set_start_* functions or
        since the start of the file if none were called.

        @return string of contents of file since start line.
        """
        logs = []
        for line in self.read_all_logs(start=self._start_line):
            logs.append(line)
        return ''.join(logs)


    def can_find(self, string):
        """ Try to find string in the logs.

        @return boolean indicating if we found the string.
        """
        return string in self.get_logs()


    def get_last_msg(self, patterns, retries=0, sleep_seconds=1):
        """Search the logs and return the latest occurrence of a message
        matching one of the patterns.

        Args:
            patterns: A regexp or a list of regexps to search the logs with.
                The function returns as soon as it finds any match to one of
                the patters, it will not search for the other patterns.
            retries: Number of times to retry if none of the patterns were
                found. Default is one attempt.
            sleep_seconds: Time to sleep between retries.

        Returns:
            The last occurrence of the first matching pattern. "None" if none
            of the patterns matched.
        """

        if not type(patterns) in (list, tuple):
            patterns = [patterns]

        for retry in xrange(retries + 1):
            for pattern in patterns:
                regexp_compiled = re.compile(pattern)
                last_match = None
                for line in self.read_all_logs():
                    if regexp_compiled.search(line):
                        last_match = line
                if last_match:
                    return last_match
            time.sleep(sleep_seconds)

        return None


class LogRotationPauser(object):
    """
    Class to control when logs are rotated from either server or client.

    Assumes all setting of CLEANUP_LOGS_PAUSED_FILE is done by this class
    and that all calls to begin and end are properly
    nested.  For instance, [ a.begin(), b.begin(), b.end(), a.end() ] is
    supported, but [ a.begin(), b.begin(), a.end(), b.end() ]  is not.
    We do support redundant calls to the same class, such as
    [ a.begin(), a.begin(), a.end() ].
    """
    def __init__(self, host=None):
        self._host = host
        self._begun = False
        self._is_nested = True


    def _run(self, command, *args, **dargs):
        if self._host:
            return self._host.run(command, *args, **dargs).exit_status
        else:
            return utils.system(command, *args, **dargs)


    def begin(self):
        """Make sure that log rotation is disabled."""
        if self._begun:
            return
        print "in begin " + str(self._begun)
        self._is_nested = (self._run(('[ -r %s ]' %
                                      CLEANUP_LOGS_PAUSED_FILE),
                                     ignore_status=True) == 0)
        print "in begin is nested: " + str(self._is_nested)
        if self._is_nested:
            print logging.__file__
            logging.info('File %s was already present' %
                         CLEANUP_LOGS_PAUSED_FILE)
            print 1
        else:
            self._run('touch ' + CLEANUP_LOGS_PAUSED_FILE)
            print 2
        self._begun = True


    def end(self):
        print "in end" + str(self._begun)
        assert self._begun
        if not self._is_nested:
            self._run('rm -f ' + CLEANUP_LOGS_PAUSED_FILE)
        else:
            logging.info('Leaving existing %s file' % CLEANUP_LOGS_PAUSED_FILE)
        self._begun = False
