# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides an object to record the output of command-line program.
"""

import fcntl
import logging
import os
import pty
import re
import subprocess
import threading
import time


class OutputRecorderError(Exception):
    """An exception class for output_recorder module."""
    pass


class OutputRecorder(object):
    """A class used to record the output of command line program.

    A thread is dedicated to performing non-blocking reading of the
    command outpt in this class. Other possible approaches include
    1. using gobject.io_add_watch() to register a callback and
       reading the output when available, or
    2. using select.select() with a short timeout, and reading
       the output if available.
    However, the above two approaches are not very reliable. Hence,
    this approach using non-blocking reading is adopted.

    To prevent the block buffering of the command output, a pseudo
    terminal is created through pty.openpty(). This forces the
    line output.

    This class saves the output in self.contents so that it is
    easy to perform regular expression search(). The output is
    also saved in a file.

    """

    DEFAULT_OPEN_MODE = 'a'
    STOP_DELAY_SECS = 1         # Delay before stopping recording.
    POLLING_DELAY_SECS = 0.1    # Delay before next polling.
    TMP_FILE = '/tmp/output_recorder.dat'

    def __init__(self, cmd, open_mode=DEFAULT_OPEN_MODE,
                 stop_delay_secs=STOP_DELAY_SECS, save_file=TMP_FILE):
        """Construction of output recorder.

        @param cmd: the command of which the output is to record.
        @param open_mode: the open mode for writing output to save_file.
                Could be either 'w' or 'a'.
        @param stop_delay_secs: the delay time before stopping the cmd.
        @param save_file: the file to save the output.

        """
        self.cmd = cmd
        self.open_mode = open_mode
        self.stop_delay_secs = stop_delay_secs
        self.save_file = save_file
        self.contents = []

        # Create a thread dedicated to record the output.
        self._recording_thread = None
        self._stop_recording_thread_event = threading.Event()

        # Use pseudo terminal to prevent buffering of the program output.
        self._master, self._slave = pty.openpty()
        self._output = os.fdopen(self._master)

        # Set non-blocking flag.
        fcntl.fcntl(self._output, fcntl.F_SETFL, os.O_NONBLOCK)


    def record(self):
        """Record the output of the cmd."""
        logging.info('Recording output of "%s".', self.cmd)
        try:
            self._recorder = subprocess.Popen(
                    self.cmd, stdout=self._slave, stderr=self._slave)
        except:
            raise OutputRecorderError('Failed to run "%s"' % self.cmd)

        with open(self.save_file, self.open_mode) as output_f:
            output_f.write(os.linesep + '*' * 80 + os.linesep)
            while True:
                try:
                    # Perform non-blocking read.
                    line = self._output.readline()
                except:
                    # Set empty string if nothing to read.
                    line = ''

                if line:
                    output_f.write(line)
                    output_f.flush()
                    # The output, e.g. the output of btmon, may contain some
                    # special unicode such that we would like to escape.
                    # In this way, regular expression search could be conducted
                    # properly.
                    self.contents.append(line.encode('unicode-escape'))
                elif self._stop_recording_thread_event.is_set():
                    self._stop_recording_thread_event.clear()
                    break
                else:
                    # Sleep a while if nothing to read yet.
                    time.sleep(self.POLLING_DELAY_SECS)


    def start(self):
        """Start the recording thread."""
        logging.info('Start recording thread.')
        self.clear_contents()
        self._recording_thread = threading.Thread(target=self.record)
        self._recording_thread.start()


    def stop(self):
        """Stop the recording thread."""
        logging.info('Stop recording thread.')
        time.sleep(self.stop_delay_secs)
        self._stop_recording_thread_event.set()
        self._recording_thread.join()

        for line in self.contents:
            logging.debug('%s', line)

        # Kill the process.
        self._recorder.terminate()
        self._recorder.kill()


    def clear_contents(self):
        """Clear the contents."""
        self.contents = []


    def get_contents(self):
        """Get the contents.

        @returns: the contents.

        """
        return self.contents


    def find(self, pattern_str, flags=re.I):
        """Find a pattern string in the contents.

        Note that the pattern_str is considered as an arbitrary literal string
        that might contain re meta-characters, e.g., '(' or ')'. Hence,
        re.escape() is applied before using re.compile.

        @param pattern_str: the pattern string to search.
        @param flags: the flags of the pattern expression behavior.

        @returns: True if found. False otherwise.

        """
        pattern = re.compile(re.escape(pattern_str), flags)
        for line in self.contents:
            result = pattern.search(line)
            if result:
                return True
        return False


if __name__ == '__main__':
    # A demo using btmon tool to monitor bluetoohd activity.
    cmd = 'btmon'
    recorder = OutputRecorder(cmd)

    if True:
        recorder.start()
        # Perform some bluetooth activities here in another terminal.
        time.sleep(recorder.stop_delay_secs)
        recorder.stop()

    for line in recorder.get_contents():
        print line
