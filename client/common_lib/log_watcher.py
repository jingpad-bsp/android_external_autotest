# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, select, sys, time
from autotest_lib.client.bin.chromeos_constants import CLEANUP_LOGS_PAUSED_FILE

class LogWatcher(object):
    """Track additions to a log file.

    This class can be used to watch a log file for new messages, even if those
    log files are periodically rolled.
    """

    def __init__(self, filename):
        """Initialize a LogWatcher object.

        Args:
          filename: The name of the file to watch.
        """
        self.SetFile(filename)
        if not os.path.exists(CLEANUP_LOGS_PAUSED_FILE):
            raise error.TestError('LogReader created without ' +
                                  CLEANUP_LOGS_PAUSED_FILE)

    def SetFile(self, filename):
        """Change the file being tracked.

        You may recycle LogWatcher objects using this method, but doing
        so from the Watch() method callback is a Bad Idea.
        """
        self.stat = os.stat(filename)
        self.fh = open(filename, "rb")
        self.filename = filename

        self.fh.seek(-1, os.SEEK_END)
        self.where = self.fh.tell()


    def ReadLine(self):
        """Read one line from the file.

        This method will read the file from scratch if it is smaller than
        the last time we read.

        Returns:
          A string containing the next line in the file, or None if there
          are no new lines in the file.
        """
        new_stat = os.stat(self.filename)
        if new_stat.st_size < self.stat.st_size:
            # assume the file file was recreated, in which case
            # we want to visit each line in the new file
            self.stat = new_stat
            self.fh.close()
            self.fh = open(self.filename, "rb")
            self.fh.seek(0)
            self.where = self.fh.tell()
            return self.ReadLine()

        self.fh.seek(-1, os.SEEK_END)
        end = self.fh.tell()
        self.fh.seek(self.where)

        if end > self.where:
            line = self.fh.readline()
            self.where = self.fh.tell()
            return line

        return None


    def Watch(self, callback, interval=1.0):
        """Watch for new lines in the file.

        This method will block while it watches the log file for new messages.
        The callback function will be invoked once for each new message that
        appears.  If callback returns False then this method stops watching
        and returns.

        Args:
          callback: A function to be invoked when a new line appears in the
            file.  This function should take a single parameter, which will
            be a string containing the next line.

          interval: An float number of seconds to sleep waiting for new
            lines.  Defaults to 1.0.
        """
        while True:
            line = self.ReadLine()
            if line:
                if not callback(line):
                    return
            else:
                time.sleep(interval)


if __name__ == '__main__':
    def p(line):
        print line,
        return True

    w = LogWatcher(sys.argv[1])
    w.Watch(p)
