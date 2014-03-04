# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re

IW_REMOTE_EVENT_LOG_FILE = '/tmp/iw_event.log'

class IwEventLogger(object):
    """Context enclosing the use of iw event logger."""
    def __init__(self, host, command_iw, local_file):
        self._host = host
        self._command_iw = command_iw
        self._local_file = local_file
        self._pid = None


    def __enter__(self):
        return self


    def __exit__(self, exception, value, traceback):
        self.stop()


    @property
    def local_file(self):
        """@return string local host path for log file."""
        return self._local_file


    def start(self):
        """Start event logger.

        This function will start iw event process in remote host, and redirect
        output to a temporary file in remote host.

        """
        command = '%s event -t > %s & echo $!' % (self._command_iw,
                                                  IW_REMOTE_EVENT_LOG_FILE)
        self._pid = int(self._host.run(command).stdout)


    def stop(self):
        """Stop event logger.

        This function will kill iw event process, and copy the log file from
        remote to local.

        """
        if self._pid is None:
            return
        # Kill iw event process
        self._host.run('kill %d' % self._pid, ignore_status=True)
        self._pid = None
        # Copy iw event log file from remote host
        self._host.get_file(IW_REMOTE_EVENT_LOG_FILE, self._local_file)
        logging.info('iw event log saved to %s', self._local_file)


    def get_association_time(self):
        """Parse local log file and return association time.

        This function will parse the iw event log to determine the time it
        takes from start of scan to being connected.
        Here are example of lines to be parsed:
            1393961008.058711: wlan0 (phy #0): scan started
            1393961019.758599: wlan0 (phy #0): connected to 04:f0:21:03:7d:bd

        @returns float number of seconds it take from start of scan to
                connected. Return None if unable to determine the time based on
                the log.

        """
        start_time = None
        end_time = None
        # Parse file to figure out the time when scanning started and the time
        # when client is connected.
        with open(self._local_file, 'r') as file:
            for line in file.readlines():
                parse_line = re.match('\s*(\d+).(\d+): (\w.*): (\w.*)', line)
                if parse_line:
                    time_integer = parse_line.group(1)
                    time_decimal = parse_line.group(2)
                    message = parse_line.group(4)
                    time_stamp = float('%s.%s' % (time_integer, time_decimal))
                    if (message.startswith('scan started') and
                            start_time is None):
                        start_time = time_stamp
                    if message.startswith('connected'):
                        if start_time is None:
                            return None
                        end_time = time_stamp
                        break;
            else:
                return None
        return end_time - start_time
