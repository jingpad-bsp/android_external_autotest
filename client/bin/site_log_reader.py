# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
from autotest_lib.client.common_lib import utils

class LogReader(object):
    """
    A class to read system log files.
    """

    def __init__(self, filename='/var/log/messages'):
        self._start_line = 1
        self._filename = filename


    def set_start_by_regexp(self, index, regexp):
        """Set the start of logs based on a regular expression.

        @param index: line matching regexp to start at, earliest log at 0.
                Negative numbers indicate matches since end of log.
        """
        regexp_compiled = re.compile(regexp)
        file_handle = open(self._filename, 'r')
        starts = []
        line_number = 1
        for line in file_handle:
            if regexp_compiled.match(line):
                starts.append(line_number)
            line_number += 1
        if index < -len(starts):
            self._start_line = 1
        elif index >= len(starts):
            self.set_start_by_current()
        else:
            self._start_line = starts[index]


    def set_start_by_reboot(self, index):
        """ Set the start of logs (must be system log) based on reboot.

        @param index: reboot to start at, earliest log at 0.  Negative
                numbers indicate reboots since end of log.
        """
        return self.set_start_by_regexp(index,
                                        r'.*000\] Linux version \d')


    def set_start_by_current(self, relative=1):
        """ Set start of logs based on current last line.

        @param relative: line relative to current to start at.  1 means
                to start the log after this line.
        """
        lines = utils.system_output('wc -l %s' % self._filename)
        self._start_line = int(lines.split(' ')[0]) + relative


    def get_logs(self):
        """ Get logs since the start line.

        Start line is set by set_start_* functions or
        since the start of the file if none were called.

        @return string of contents of file since start line.
        """
        return utils.system_output('tail -n +%d %s' %
                                   (self._start_line, self._filename))

    def can_find(self, string):
        """ Try to find string in the logs.

        @return boolean indicating if we found the string.
        """
        return string in self.get_logs()
