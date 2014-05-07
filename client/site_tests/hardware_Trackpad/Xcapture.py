# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

''' A module for capturing X events '''

import logging
import os
import re
import subprocess
import tempfile
import time

import common_util
import trackpad_util
import Xevent

from trackpad_util import Display, read_trackpad_test_conf
from Xevent import reset_x_input_prop, set_x_input_prop


class Mtplot:
    ''' Create a mtplot window for Xcapture to listen to '''

    def __init__(self, display, error):
        display.set_environ()
        self.error = error
        self._create_mtplot_window()
        self.id = self._get_mtplot_win_id()
        if self.id is None:
            raise error.TestError('Failure on deriving window id in focus.')

    def _create_mtplot_window(self):
        trackpad_device_file, msg = trackpad_util.get_trackpad_device_file()
        mtplot_cmd = 'mtplot -c 0 %s' % trackpad_device_file
        self.null_file = open('/dev/null')

        try:
            self.proc = subprocess.Popen(mtplot_cmd.split(),
                                         stdout=self.null_file)
        except:
            err_msg = 'Cannot start program: %s' % mtplot_cmd
            raise self.error.TestError(err_msg)

        time.sleep(0.1)
        if self.proc.poll() is not None:
            raise self.error.TestError('Failure on "%s" [%d]' %
                                       (mtplot_cmd, self.proc.returncode))

        logging.info('"%s" has been launched.' % mtplot_cmd)

    def _get_mtplot_win_id(self):
        '''Use xwininfo to derive the window id of mtplot.'''
        # A typical mtplot window info in xwininfo is
        #      0x800001 "mtplot": ()  2560x1700+0+0  +0+0
        cmd = 'xwininfo -root -tree | grep mtplot'
        win_info = common_util.simple_system_output(cmd)
        win_id = win_info.strip().split()[0] if win_info else None
        return win_id

    def destroy(self):
        ''' Destroy the mtplot process. '''
        self.proc.terminate()
        self.proc.kill()
        self.proc.wait()
        self.null_file.close()


class Xcapture:
    ''' A class to capture X events '''

    def __init__(self, error, conf_path):
        # Set X display server and xauthority.
        self.display = Display()
        self.display.set_environ()

        self.xcapture_dir = '/tmp/xevent'
        self.fd = None
        self.proc = None
        self.error = error
        self.conf_path = conf_path

        # Create the directory if not existent.
        if not os.path.exists(self.xcapture_dir):
            try:
                os.mkdir(self.xcapture_dir)
            except OSError:
                err_msg = 'Fail to make directory: %s' % self.xcapture_dir
                raise self.error.TestError(err_msg)

        # Create a tmp file to capture the X events for all gesture files
        self.fd_all = tempfile.NamedTemporaryFile()
        self.xcapture_file_all = self.fd_all.name

        # Enable X Scroll Buttons and Tap Enable if they are not enabled yet
        self.scroll_butons = set_x_input_prop(Xevent.X_PROP_SCROLL_BUTTONS)
        self.tap_enable = set_x_input_prop(Xevent.X_PROP_TAP_ENABLE)

        # Launch the capture process
        mtplot_gui = read_trackpad_test_conf('mtplot_gui', conf_path)
        if mtplot_gui:
            self.mtplot = Mtplot(self.display, error)
            self.xcapture_cmd = 'xev -id %s' % self.mtplot.id
        else:
            self.mtplot = None
            self.xcapture_cmd = 'xev -geometry %s' % self._root_geometry()
        self._launch(self.fd_all)

        logging.info('X events will be saved in %s' % self.xcapture_dir)
        logging.info('X events capture command: %s' % self.xcapture_cmd)

    def _root_geometry(self):
        """Get the geometry of the root window.

        The geometry string looks like:
            -geometry 2560x1700+0+0
        """
        cmd = 'xwininfo -root | grep geometry'
        geometry_str = common_util.simple_system_output(cmd)
        _, geometry = geometry_str.split()
        return geometry

    def _open_file(self, filename):
        try:
            fd = open(filename, 'w+')
        except:
            err_msg = 'Cannot open file to save X events: %s'
            raise self.error.TestError(err_msg % filename)
        return fd

    def _launch(self, fd):
        ''' Launch the capture program '''
        try:
            self.proc = subprocess.Popen(self.xcapture_cmd.split(), stdout=fd)
        except:
            err_msg = 'Cannot start capture program: %s' % self.xcapture_cmd
            raise self.error.TestError(err_msg)

    def start(self, filename):
        ''' Start capture program '''
        self.display.move_cursor_to_center()
        self.xcapture_file = os.path.join(self.xcapture_dir, filename) + '.xev'
        self.fd = self._open_file(self.xcapture_file)

    def wait(self):
        ''' Wait until timeout or max_post_replay_time expires.
        The wait loop is terminated if either of the conditions is true:
        (Cond 1) Normal timeout: there are no more X events coming in
                 before timeout; or
        (Cond 2) Endless xevents: the duration of X event emission after the
                 completion of playback, typically observed in coasting,
                 exceeds max_post_replay_time. In this case, the X events
                 keep coming in for a while. We need to interrupt it after
                 max_post_replay_time expires so that the waiting will not
                 last forever due to a possible driver bug.
        '''
        timeout_str = 'xcapture_timeout'
        max_time_str = 'xcapture_max_post_replay_time'
        conf_path = self.conf_path
        timeout = read_trackpad_test_conf(timeout_str, conf_path)
        max_post_replay_time = read_trackpad_test_conf(max_time_str, conf_path)
        interval = timeout / 10.0

        with open(self.xcapture_file_all) as fd_all:
            now = latest_event_time = start_time = time.time()
            # Cond2: keep looping while cond2 does not occur
            while (now - start_time <= max_post_replay_time):
                time.sleep(interval)
                now = time.time()
                if fd_all.read():
                    latest_event_time = now
                # Cond1: if cond1_normal_timeout occurs, exit the loop
                if (now - latest_event_time > timeout):
                    return True
            else:
                # Cond2 occurs
                max_warn = 'Warning: max_post_replay_time (%d seconds) expires'
                logging.info(max_warn % max_post_replay_time)
                return False

    def read(self):
        ''' Read packet data from the device file '''
        with open(self.xcapture_file) as fd:
            return fd.readlines()

    def stop(self):
        ''' Make a copy of the X events and close the file '''
        fd_is_open = self.fd is not None and not self.fd.closed
        fd_all_is_open = self.fd_all is not None and not self.fd_all.closed
        if fd_is_open:
            if fd_all_is_open:
                # Make a copy of the X events for this gesture file
                self.fd_all.seek(os.SEEK_SET)
                self.fd.write(self.fd_all.read())
                # Truncate xcapture_file_all
                self.fd_all.seek(os.SEEK_SET)
                self.fd_all.truncate()
            # Close the X event capture file for this gesture file
            self.fd.flush()
            os.fsync(self.fd.fileno())
            self.fd.close()
            self.fd = None

    def terminate(self):
        ''' Terminate the X capture subprocess and destroy the popup window '''
        # Terminate the X capture subprocess
        if self.fd_all is not None and not self.fd_all.closed:
            self.fd_all.close()
            self.fd_all = None
        self.proc.terminate()
        self.proc.kill()
        self.proc.wait()

        # Destroy the mtplot window if exists.
        if self.mtplot:
            self.mtplot.destroy()

        # Reset X Scroll Buttons and Tap Enable if they were disabled originally
        reset_x_input_prop(self.scroll_butons)
        reset_x_input_prop(self.tap_enable)
