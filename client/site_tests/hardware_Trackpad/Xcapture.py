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

from trackpad_util import Display, read_trackpad_test_conf


def create_popup_window(display, ax):
    ''' Create a popup window with override-redirect so that we can
        manipulate its geometry.
    '''
    # win_x, win_y: the coordinates of the popup window
    # win_width, win_height: the width and height of the popup window
    win_x = 0
    win_y = 0
    win_width = display.screen.width_in_pixels
    win_height = display.screen.height_in_pixels
    win_geometry = (win_x, win_y, win_width, win_height)
    logging.info('Geometry of the popup window: %dx%d+%d+%d' %
                 (win_width, win_height, win_x, win_y))

    # Create the popup window
    popup_win = ax.create_and_map_window(x=win_x,
                                         y=win_y,
                                         width=win_width,
                                         height=win_height,
                                         title='Xcapture_Popup',
                                         override_redirect=True)
    popup_info = ax.get_window_info(popup_win.id)

    # Check that the popup window appears in the required position.
    # The default timeout of await_condition is 10 seconds, which looks
    # reasonable here too.
    try:
        ax.await_condition(
                lambda: popup_info.get_geometry() == win_geometry,
                desc='Check window 0x%x\'s geometry' % popup_win.id)
    except ax.ConditionTimeoutError as exception:
        raise error.TestFail('Timed out on condition: %s' %
                             exception.__str__())

    return popup_win


class Mtplot:
    ''' Create a mtplot window for Xcapture to listen to '''

    def __init__(self, display):
        display.set_environ()
        self._create_mtplot_window(display)
        self.id = self._get_mtplot_win_id()
        if self.id is None:
            raise error.TestError('Failure on deriving window id in focus.')

    def _create_mtplot_window(self, display):
        trackpad_device_file, msg = trackpad_util.get_trackpad_device_file()
        mtplot_cmd = 'mtplot %s' % trackpad_device_file
        self.null_file = open('/dev/null')

        try:
            self.proc = subprocess.Popen(mtplot_cmd.split(),
                                         stdout=self.null_file)
        except:
            err_msg = 'Cannot start program: %s' % self.mtplot_cmd
            raise self.error.TestError(err_msg)

        time.sleep(0.1)
        if self.proc.poll() is not None:
            raise error.TestError('Failure on "%s" [%d]' %
                                  (self.mtplot_cmd, self.proc.returncode))

        logging.info('"%s" has been launched.' % mtplot_cmd)

    def _get_mtplot_win_id(self):
        ''' Use xwininfo to make sure that the focus window is not Chrome '''
        count = 0
        max_count = 50
        while count <= max_count:
            focus_win_id = self._get_focus_window_id()
            if (self._is_full_screen(focus_win_id) and
                not self._is_chrome(focus_win_id)):
                return int(focus_win_id, 16)
            logging.info('    Waiting mtplot window to get in focus (%d)...' %
                         count)
            time.sleep(0.1)
            count += 1
        raise error.TestError('Fail to get mtplot window in focus')

    def _is_chrome(self, win_id):
        ''' Use xwininfo to get window name '''
        cmd = 'xwininfo -root -tree | grep %s' % win_id
        win_info = common_util.simple_system_output(cmd)
        # The win_info for a chrome browser looks like
        #     0x600016 "chrome": ("chrome" "Chrome")  1366x768+-1366+0 +-1366+0
        if win_info is not None:
            res = re.search('chrome', win_info, re.I)
            if res is not None:
                return True
        return False

    def _is_full_screen(self, win_id):
        ''' Does the window occupy the whole screen? '''
        cmd = 'xwininfo -root -tree | grep %s' % win_id
        win_info = common_util.simple_system_output(cmd)
        full_screen_dim = self._get_screen_dimensions()
        if full_screen_dim is None:
            raise error.TestError('Failure on deriving screen dimensions.')

        # The win_info for a chrome browser looks like
        #     0x600016 "chrome": ("chrome" "Chrome")  1366x768+-1366+0 +-1366+0
        if win_info is not None:
            res = re.search(full_screen_dim, win_info, re.I)
            if res is not None:
                return True
        return False

    def _get_screen_dimensions(self):
        ''' Use xdpyinfo to derive the screen dimensions such as 1366x768 '''
        cmd = 'xdpyinfo | grep dimensions'
        dim = common_util.simple_system_output(cmd)
        if dim is not None:
            # An example output:
            #   "  dimensions:    1366x768 pixels (361x203 millimeters)"
            res = re.search('\s*dimensions:\s*(\d+)x(\d+)\s*pixels', dim, re.I)
            if res is not None:
                return '%sx%s' % (res.group(1), res.group(2))
        return None


    def _get_focus_window_id(self):
        ''' Use xdpyinfo to derive the window id currently in focus '''
        cmd = 'xdpyinfo | grep focus'
        win_id = common_util.simple_system_output(cmd)
        if win_id is not None:
            # An example output: "focus:  window 0x600017, revert to Parent"
            res = re.search('focus:\s+window\s+0x(\w+),', win_id, re.I)
            if res is not None:
                return res.group(1)
        return None

    def destroy(self):
        ''' Destroy the mtplot process. '''
        self.proc.terminate()
        self.proc.kill()
        self.proc.wait()
        self.null_file.close()


class Xcapture:
    ''' A class to capture X events '''

    def __init__(self, error, conf_path, autox):
        # Set X display server and xauthority.
        self.display = Display()
        self.display.set_environ()
        self.ax = autox

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

        # Create a window to listen to the X events
        mtplot_gui = read_trackpad_test_conf('mtplot_gui', conf_path)
        if mtplot_gui:
            self.win = Mtplot(self.display)
        else:
            self.win = create_popup_window(self.display, self.ax)

        # Launch the capture process
        self.xcapture_cmd = 'xev -id 0x%x' % int(self.win.id)
        self._launch(self.fd_all)

        logging.info('X events will be saved in %s' % self.xcapture_dir)
        logging.info('X events capture program: %s' % self.xcapture_cmd)

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
                if fd_all.read() != '':
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

        # Destroy the popup window
        self.win.destroy()
        self.ax.sync()
