# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

''' A module for capturing X events '''

import logging
import os
import subprocess
import time

from trackpad_util import Display, read_trackpad_test_conf


class Xcapture:
    ''' A class to capture X events '''

    def __init__(self, error, conf_path):
        # Set X display server and xauthority.
        self.display = Display()
        self.display.set_environ()

        self.xcapture_dir = '/tmp/xevent'
        self.fd = None
        self.proc = None
        self.xcapture_cmd = 'xev'
        self.error = error
        self.conf_path = conf_path

        # Create the directory if not existent.
        if not os.path.exists(self.xcapture_dir):
            try:
                os.makedir(self.xcapture_dir)
            except OSError:
                err_msg = 'Fail to make directory: %s' % self.xcapture_dir
                raise self.error.TestError(err_msg)
        logging.info('X events will be saved in %s' % self.xcapture_dir)
        logging.info('X events capture program: %s' % self.xcapture_cmd)

    def start(self, filename):
        ''' Start capture program '''
        self.xcapture_file = os.path.join(self.xcapture_dir, filename) + '.xev'
        self.display.move_cursor_to_center()

        # Open the temporary file to save X events
        try:
            self.fd = open(self.xcapture_file, 'w+')
        except:
            err_msg = 'Cannot open file to save X events: %s'
            raise self.error.TestError(err_msg % self.xcapture_file)

        # Start the capture program
        try:
            self.proc = subprocess.Popen(self.xcapture_cmd.split(),
                                          stdout=self.fd)
        except:
            err_msg = 'Cannot start capture program: %s' % self.xcapture_cmd
            raise self.error.TestError(err_msg)

    def wait(self):
        ''' Wait until timeout or max_post_replay_time expires.
        The wait loop is terminated if either of the conditions is true:
        (1) there are no more X events coming in before timeout; or
        (2) the duration of X event emission after the completion of playback,
            typically observed in coasting, exceeds max_post_replay_time.
            In this case, the X events keep coming in for a while. We need to
            interrupt it after max_post_replay_time expires so that the
            waiting will not last forever due to a possible driver bug.
        '''
        timeout_str = 'xcapture_timeout'
        max_time_str = 'xcapture_max_post_replay_time'
        conf_path = self.conf_path
        timeout = read_trackpad_test_conf(timeout_str, conf_path)
        max_post_replay_time = read_trackpad_test_conf(max_time_str, conf_path)
        interval = timeout / 10.0

        with open(self.xcapture_file) as fd:
            start_time = time.time()
            latest_event_time = start_time
            while True:
                time.sleep(interval)
                now = time.time()
                content = fd.read()
                if content != '':
                    latest_event_time = now
                else:
                    if now - latest_event_time > timeout:
                        break
                if now - start_time > max_post_replay_time:
                    max_warn = 'max_post_replay_time (%d seconds) expires'
                    logging.info(max_warn % max_post_replay_time)
                    break

    def read(self):
        ''' Read packet data from the device file '''
        with open(self.xcapture_file) as fd:
            return fd.readlines()

    def stop(self):
        ''' Close the device file and terminate the X capturing program '''
        if self.fd is not None:
            # Flush the X event file
            self.fd.flush()
            os.fsync(self.fd.fileno())
            # Close the X event file
            self.fd.close()
            self.fd = None

        # terminate xcapture subprocess
        self.proc.terminate()
        self.proc.kill()
        self.proc.wait()
