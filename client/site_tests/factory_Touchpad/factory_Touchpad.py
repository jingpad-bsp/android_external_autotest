# -*- coding: utf-8 -*-
#
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# Intended for use during manufacturing to validate that the touchpad
# is functioning properly.

import cairo
import gobject
import gtk
import os
import pty
import re
import subprocess
import sys
import time

from cmath import pi
from glob import glob
from gtk import gdk

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test
from autotest_lib.client.bin.input.input_device import *
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.common_lib.error import CmdError


_X_SEGMENTS = 5
_Y_SEGMENTS = 4

_X_TP_OFFSET = 12
_Y_TP_OFFSET = 12
_TP_WIDTH = 396
_TP_HEIGHT = 212
_TP_SECTOR_WIDTH = (_TP_WIDTH / _X_SEGMENTS) - 1
_TP_SECTOR_HEIGHT = (_TP_HEIGHT / _Y_SEGMENTS) - 1

_X_SP_OFFSET = 428
_SP_WIDTH = 15

_F_RADIUS = 21

_X_OF_OFFSET = 486 + _F_RADIUS + 2
_Y_OF_OFFSET = 54 + _F_RADIUS + 2

_X_TFL_OFFSET = 459 + _F_RADIUS + 2
_X_TFR_OFFSET = 513 + _F_RADIUS + 2
_Y_TF_OFFSET = 117 + _F_RADIUS + 2


class TouchpadTest:

    def __init__(self, tp_image, drawing_area):
        self._tp_image = tp_image
        self._drawing_area = drawing_area
        self._motion_grid = {}
        for x in range(_X_SEGMENTS):
            for y in range(_Y_SEGMENTS):
                self._motion_grid['%d,%d' % (x, y)] = False
        self._scroll_array = {}
        for y in range(_Y_SEGMENTS):
            self._scroll_array[y] = False
        self._l_click = False
        self._r_click = False
        self._of_z_rad = 0
        self._tf_z_rad = 0
        self._deadline = None

    def calc_missing_string(self):
        missing = []
        missing_motion_sectors = sorted(
            i for i, v in self._motion_grid.items() if v is False)
        if missing_motion_sectors:
            missing.append('Missing following motion sectors\n'
                           '未偵測到下列位置的觸控移動訊號 [%s]' %
                           ', '.join(missing_motion_sectors))
        missing_scroll_segments = sorted(
            str(i) for i, v in self._scroll_array.items() if v is False)
        if missing_scroll_segments:
            missing.append('Missing following scroll segments\n'
                           '未偵測到下列位置的觸控捲動訊號 [%s]' %
                           ', '.join(missing_scroll_segments))
        if not self._l_click:
            missing.append('Missing left click\n'
                           '沒有偵測到左鍵被按下，請檢修')
        if not self._r_click:
            missing.append('Missing right click\n'
                           '沒有偵測到右鍵被按下，請檢修')
        return '\n'.join(missing)

    def timer_event(self, countdown_label):
        if not self._deadline:  # Ignore timer with no countdown in progress.
            return True
        time_remaining = max(0, self._deadline - time.time())
        if time_remaining == 0:
            factory.log('deadline reached')
            gtk.main_quit()
        countdown_label.set_text('%d' % time_remaining)
        countdown_label.queue_draw()
        return True

    def device_event(self, x, y, z, fingers, left, right):
        x_seg = int(round(x / (1.0 / float(_X_SEGMENTS - 1))))
        y_seg = int(round(y / (1.0 / float(_Y_SEGMENTS - 1))))
        z_rad = int(round(z / (1.0 / float(_F_RADIUS - 1))))

        index = '%d,%d' % (x_seg, y_seg)

        assert(index in self._motion_grid)
        assert(y_seg in self._scroll_array)

        new_stuff = False

        if left and not self._l_click:
            self._l_click = True
            self._of_z_rad = _F_RADIUS
            factory.log('ok left click')
            new_stuff = True
        elif right and not self._r_click:
            self._r_click = True
            self._tf_z_rad = _F_RADIUS
            factory.log('ok right click')
            new_stuff = True

        if fingers == 1 and not self._motion_grid[index]:
            self._motion_grid[index] = True
            new_stuff = True
        elif fingers == 2 and not self._scroll_array[y_seg]:
            self._scroll_array[y_seg] = True
            new_stuff = True

        if fingers == 1 and not self._l_click and z_rad != self._of_z_rad:
            self._of_z_rad = z_rad
            new_stuff = True
        elif fingers == 2 and not self._r_click and z_rad != self._tf_z_rad:
            self._tf_z_rad = z_rad
            new_stuff = True

        if new_stuff:
            self._drawing_area.queue_draw()
            if self._deadline is None:
                self._deadline = int(time.time()) + ful.FAIL_TIMEOUT

        if not self.calc_missing_string():
            factory.log('completed successfully')
            gtk.main_quit()

    def expose_event(self, widget, event):
        context = widget.window.cairo_create()

        # Show touchpad image as the background.
        context.set_source_surface(self._tp_image, 0, 0)
        context.paint()

        context.set_source_rgba(*ful.RGBA_GREEN_OVERLAY)

        for index in self._motion_grid:
            if not self._motion_grid[index]:
                continue
            ind_x, ind_y = map(int, index.split(','))
            x = _X_TP_OFFSET + (ind_x * (_TP_SECTOR_WIDTH + 1))
            y = _Y_TP_OFFSET + (ind_y * (_TP_SECTOR_HEIGHT + 1))
            coords = (x, y, _TP_SECTOR_WIDTH, _TP_SECTOR_HEIGHT)
            context.rectangle(*coords)
            context.fill()

        for y_seg in self._scroll_array:
            if not self._scroll_array[y_seg]:
                continue
            y = _Y_TP_OFFSET + (y_seg * (_TP_SECTOR_HEIGHT + 1))
            coords = (_X_SP_OFFSET, y, _SP_WIDTH, _TP_SECTOR_HEIGHT)
            context.rectangle(*coords)
            context.fill()

        if not self._l_click:
            context.set_source_rgba(*ful.RGBA_YELLOW_OVERLAY)

        context.arc(_X_OF_OFFSET, _Y_OF_OFFSET, self._of_z_rad, 0.0, 2.0 * pi)
        context.fill()

        if self._l_click and not self._r_click:
            context.set_source_rgba(*ful.RGBA_YELLOW_OVERLAY)

        context.arc(_X_TFL_OFFSET, _Y_TF_OFFSET, self._tf_z_rad, 0.0, 2.0 * pi)
        context.fill()
        context.arc(_X_TFR_OFFSET, _Y_TF_OFFSET, self._tf_z_rad, 0.0, 2.0 * pi)
        context.fill()

        return True

    def button_press_event(self, widget, event):
        factory.log('button_press_event %d,%d' % (event.x, event.y))
        return True

    def button_release_event(self, widget, event):
        factory.log('button_release_event %d,%d' % (event.x, event.y))
        return True

    def motion_event(self, widget, event):
        factory.log('motion_event %d,%d' % (event.x, event.y))
        return True


class SynClient:
    _SETTINGS_CMDLINE = '/usr/bin/synclient -l'
    _CMDLINE = '/usr/bin/synclient -m 50'

    def __init__(self, test):
        self._test = test
        try:
            settings_data = utils.system_output(self._SETTINGS_CMDLINE)
        except CmdError as e:
            raise error.TestError('Failure on "%s" [%d]' %
                                  (self._SETTINGS_CMDLINE,
                                   e.args[1].exit_status))
        settings = {}
        for line in settings_data.split('\n'):
            cols = [x for x in line.rstrip().split(' ') if x]
            if len(cols) != 3 or cols[1] != '=':
                continue
            settings[cols[0]] = cols[2]
        try:
            for key, attr in (('LeftEdge',   '_xmin'),
                              ('RightEdge',  '_xmax'),
                              ('TopEdge',    '_ymin'),
                              ('BottomEdge', '_ymax'),
                              ('FingerLow',  '_zmin'),
                              ('FingerHigh', '_zmax')):
                v = float(settings[key])
                setattr(self, attr, v)
        except KeyError as e:
            factory.log('Field %s does not exist' % e.args)
            raise error.TestNAError("Can't detect all hardware information")
        except ValueError as e:
            factory.log('Invalid literal format of %s: %s' % (key, e.args[0]))
            raise error.TestNAError("Can't understand all hardware information")
        try:
            self._proc = subprocess.Popen(self._CMDLINE.split(),
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE)
        except OSError as e:
            raise error.TestError('Failure on launching "%s"' % self._CMDLINE)
        # delay before we poll
        time.sleep(0.1)
        if self._proc.poll() is not None:
            if self._proc.returncode != 0:
                raise error.TestError('Failure on "%s" [%d]' %
                                      (self._CMDLINE, self._proc.returncode))
            else:
                raise error.TestError('Termination unexpected on "%s"' %
                                      self._CMDLINE)
        gobject.io_add_watch(self._proc.stdout, gobject.IO_IN, self.recv)

    def recv(self, src, cond):
        ''' header and data look as:
            time     x    y   z f  w  l r u d m     multi  gl gm gr gdx gdy
           0.000  3532 3807   0 0  0  0 0 0 0 0  00000000
        '''
        data = self._proc.stdout.readline().split()
        if data[0] == 'time':
            return True
        if len(data) != 12:
            factory.log('unknown data : %d, %s' % (len(data), data))
            return True
        data_x, data_y, data_z, f, w, l, r = data[1:8]
        x = sorted([self._xmin, float(data_x), self._xmax])[1]
        x = (x - self._xmin) / (self._xmax - self._xmin)
        y = sorted([self._ymin, float(data_y), self._ymax])[1]
        y = (y - self._ymin) / (self._ymax - self._ymin)
        z = sorted([self._zmin, float(data_z), self._zmax])[1]
        z = (z - self._zmin) / (self._zmax - self._zmin)
        # Detect right click button or alt right click
        alt_r = int(r) or (int(l) and int(f) == 2)
        self._test.device_event(x, y, z, int(f), int(l), alt_r)
        return True

    def quit(self):
        factory.log('killing SynClient ...')
        self._proc.kill()
        factory.log('dead')


class EvdevClient:

    def __init__(self, test, device):
        self._test = test
        self.ev = InputEvent()
        self.device = device
        gobject.io_add_watch(device.f, gobject.IO_IN, self.recv)

        self._xmin = device.get_x_min()
        self._xmax = device.get_x_max()
        self._ymin = device.get_y_min()
        self._ymax = device.get_y_max()
        self._zmin = device.get_pressure_min()
        self._zmax = device.get_pressure_max()

        factory.log('x:(%d : %d), y:(%d : %d), z:(%d, %d)' %
                    (self._xmin, self._xmax, self._ymin, self._ymax,
                     self._zmin, self._zmax))

    def _to_percent(self, val, _min, _max):
        bound = sorted([_min, float(val), _max])[1]
        return (bound - _min) / (_max - _min)

    def recv(self, src, cond):
        try:
            self.ev.read(src)
        except:
            raise error.TestError('Error reading events from %s' %
                                  self.device.path)
        if not self.device.process_event(self.ev):
            return True

        f = self.device.get_num_fingers()
        if f == 0:
           return True

        x = self.device.get_x()
        y = self.device.get_y()
        z = self.device.get_pressure()
        l = self.device.get_left()
        # Detect right click button or alt right click
        r = self.device.get_right() or (l and f == 2)

        # Convert raw coordinate to % of range.
        x_pct = self._to_percent(x, self._xmin, self._xmax)
        y_pct = self._to_percent(y, self._ymin, self._ymax)
        z_pct = self._to_percent(z, self._zmin, self._zmax)

        factory.log('x=%f y=%f z=%f f=%d l=%d r=%d' %
                    (x_pct, y_pct, z_pct, f, l, r))

        self._test.device_event(x_pct, y_pct, z_pct, f, l, r)
        return True

    def quit(self):
        if self.device and self.device.f and not self.device.f.closed:
            factory.log('Closing %s...' % self.device.path)
            self.device.f.close()


class SynControl:
    ''' Use syncontrol to read packets and pass them to TouchpadTest '''
    # A typical packet looks like
    #     x: 4357, y: 2973, z: 48, w: 4, dx: 0, dy: 0,
    #     finger_index: 0, left_button: 0, right_button: 0
    pattern = (u'x: \d+, y: \d+, z: \d+, w: \d+, dx: -?\d+, dy: -?\d+, '
               u'finger_index: \d+, left_button: \d+, right_button: \d+')
    _SYNCONTROL = '/opt/Synaptics/bin/syncontrol'
    _CMDLINE = '%s packets' % _SYNCONTROL

    # Set the default min and max values for typical bezel limits and Z.
    # These are approximate values, and may be different in different models.
    # Use these values only if they cannot be derived from the diag file.
    _X_RANGE = (1400, 5400)
    _Y_RANGE = (1300, 4300)
    _Z_RANGE = (0, 255)

    def __init__(self, test):
        self._test = test
        # Read settings from diag file
        self._get_settings()

        # Open pty to avoid buffered output in subprocess.Popen
        master, slave = pty.openpty()
        self.pty_stdout = os.fdopen(master)
        self._count = 0

        try:
            self._proc = subprocess.Popen(self._CMDLINE, shell=True,
                                          stdout=slave, stderr=slave)
        except OSError as e:
            raise error.TestError('Failure on launching "%s"' % self._CMDLINE)

        if self._proc.poll() is not None:
            if self._proc.returncode != 0:
                raise error.TestError('Failure on "%s" [%d]' %
                                      (self._CMDLINE, self._proc.returncode))
            else:
                raise error.TestError('Termination unexpected on "%s"' %
                                      self._CMDLINE)
        gobject.io_add_watch(self.pty_stdout, gobject.IO_IN, self.recv)

    def _get_settings(self):
        ''' Get min x, min y, max x, max y, and max z '''

        def _delete_diag_files(tmp_dir, diag_file):
            for f in glob(os.path.join(tmp_dir, diag_file)):
                if os.path.isfile(f):
                    os.remove(f)

        tmp_dir = '/tmp'
        diag_file = 'SynDiag*'
        diag_cmd = 'HOME=%s %s diag' % (tmp_dir, self._SYNCONTROL)

        # delete any old diag file
        _delete_diag_files(tmp_dir, diag_file)

        # Execute syncontrol diag to dump touchpad settings
        utils.system(diag_cmd)

        # Initialize the settings
        # Note: there is no min z in the diag file. Set it to default value 0.
        self._xmin, self._xmax = self._X_RANGE
        self._ymin, self._ymax = self._Y_RANGE
        self._zmin, self._zmax = self._Z_RANGE
        found_z = False
        found_rect = False

        # A bezel rectangle in diag file looks as:
        #       'Bezel Rectangle (1374, 1324) (5538, 4464)'
        # The max z in diag file looks as:
        #       'Maximum Z       255'
        rect_str = u'Bezel Rectangle\s+\((\d+),\s*(\d+)\)\s*\((\d+),\s*(\d+)\)'

        diag = glob(os.path.join(tmp_dir, diag_file))
        if diag != []:
            factory.log('diag_file: %s' % diag)
            with open(diag[0]) as f:
                for line in f:
                    # Read min x, min y, max x, max y from the bezel rectangle
                    if not found_rect and line.startswith('Bezel Rectangle'):
                        s = re.search(rect_str, line)
                        if s is not None:
                            self._xmin = int(s.group(1))
                            self._ymin = int(s.group(2))
                            self._xmax = int(s.group(3))
                            self._ymax = int(s.group(4))
                            found_rect = True
                    # Read max z
                    elif not found_z and line.startswith('Maximum Z'):
                        self._zmax = int(line.split()[-1])
                        found_z = True
                    if found_rect and found_z:
                        break

        # delete the diag file
        _delete_diag_files(tmp_dir, diag_file)

    def recv(self, src, cond):
        line = self.pty_stdout.readline()
        if line == '':
            return True

        # check packet validity
        if re.search(self.pattern, line) is None:
            factory.log('  Invalid packet skipped: %s' % line)
            return True

        data = line.split(',')
        self._count += 1
        (data_x, data_y, data_z, data_w, data_dx, data_dy, data_finger_index,
                 data_left_button, data_right_button) = \
                 (d.split(':')[-1].strip().rstrip('\n') for d in data)

        x = sorted([self._xmin, float(data_x), self._xmax])[1]
        x = (x - self._xmin) / (self._xmax - self._xmin)
        y = sorted([self._ymin, float(data_y), self._ymax])[1]
        y = (y - self._ymin) / (self._ymax - self._ymin)
        y = 1 - y
        z = sorted([self._zmin, float(data_z), self._zmax])[1]
        z = (z - self._zmin) / (self._zmax - self._zmin)
        fingers = int(data_finger_index) + 1
        left_button = int(data_left_button)
        right_button = int(data_right_button)
        self._test.device_event(x, y, z, fingers, left_button, right_button)
        return True

    def quit(self):
        factory.log('killing SynControl ...')
        self._proc.kill()
        factory.log('dead')


class factory_Touchpad(test.test):
    version = 1
    preserve_srcdir = True

    def run_once(self):

        factory.log('%s run_once' % self.__class__)

        os.chdir(self.srcdir)
        tp_image = cairo.ImageSurface.create_from_png('touchpad.png')
        image_size = (tp_image.get_width(), tp_image.get_height())

        drawing_area = gtk.DrawingArea()

        test = TouchpadTest(tp_image, drawing_area)

        drawing_area.set_size_request(*image_size)
        drawing_area.connect('expose_event', test.expose_event)
        drawing_area.connect('button-press-event', test.button_press_event)
        drawing_area.connect('button-release-event', test.button_release_event)
        drawing_area.connect('motion-notify-event', test.motion_event)
        drawing_area.add_events(gdk.EXPOSURE_MASK |
                                gdk.BUTTON_PRESS_MASK |
                                gdk.BUTTON_RELEASE_MASK |
                                gdk.POINTER_MOTION_MASK)

        countdown_widget, countdown_label = ful.make_countdown_widget()
        gobject.timeout_add(1000, test.timer_event, countdown_label)

        test_widget = gtk.VBox()
        test_widget.set_spacing(20)
        test_widget.pack_start(drawing_area, False, False)
        test_widget.pack_start(countdown_widget, False, False)

        raw_dev = glob('/dev/serio_raw*')
        # Check if synaptics closed source kernel driver is used
        if len(raw_dev) > 0:
            factory.log('Syncontrol: found device: %s' % raw_dev[0])
            touchpad = SynControl(test)
        else:
            # Detect an evdev compatible touchpad device.
            # TODO(djkurtz): Use gudev to detect touchpad
            for evdev in glob('/dev/input/event*'):
                device = InputDevice(evdev)
                if device.is_touchpad():
                    break
            else:
                device = None

            # Using EvdevCient if an evdev compatible touchpad device is found
            if device:
                factory.log('EvdevClient: using %s,  device %s' %
                            (device.name, device.path))
                touchpad = EvdevClient(test, device)
            else:
                factory.log('Using SynClient.')
                touchpad = SynClient(test)

        ful.run_test_widget(self.job, test_widget,
            cleanup_callback=touchpad.quit)

        missing = test.calc_missing_string()
        if missing:
            raise error.TestFail(missing)

        factory.log('%s run_once finished' % self.__class__)
