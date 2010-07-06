# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import cairo
import gobject
import gtk
import pango
import time
import os
import sys
import subprocess

from cmath import pi

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


_SYNCLIENT_SETTINGS_CMDLINE = '/usr/bin/synclient -l'
_SYNCLIENT_CMDLINE = '/usr/bin/synclient -m 50'

_RGBA_GREEN_OVERLAY = (0, 0.5, 0, 0.6)
_RGBA_YELLOW_OVERLAY = (0.5, 0.5, 0, 0.6)

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

    def __init__(self, tp_image, drawing_area, ft_state):
        self._tp_image = tp_image
        self._drawing_area = drawing_area
        self._ft_state = ft_state
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

    def timer_event(self, window):
        if not self._deadline:
            # Ignore timer events with no countdown in progress.
            return True
        if self._deadline <= time.time():
            XXX_log('deadline reached')
            gtk.main_quit()
        window.queue_draw()
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

        missing_motion_sectors = set(i for i, v in self._motion_grid.items()
                                     if v is False)
        missing_scroll_segments = set(i for i, v in self._scroll_array.items()
                                      if v is False)
        # XXX add self._r_click here when that is supported...
        if (self._l_click
            and not missing_motion_sectors
            and not missing_scroll_segments):
            gtk.main_quit()

    def expose_event(self, widget, event):
        context = widget.window.cairo_create()

        context.set_source_surface(self._tp_image, 0, 0)
        context.paint()

        context.set_source_rgba(*_RGBA_GREEN_OVERLAY)

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
            context.set_source_rgba(*_RGBA_YELLOW_OVERLAY)

        context.arc(_X_OF_OFFSET, _Y_OF_OFFSET, self._of_z_rad, 0.0, 2.0 * pi)
        context.fill()

        if self._l_click and not self._r_click:
            context.set_source_rgba(*_RGBA_YELLOW_OVERLAY)

        context.arc(_X_TFL_OFFSET, _Y_TF_OFFSET, self._tf_z_rad, 0.0, 2.0 * pi)
        context.fill()
        context.arc(_X_TFR_OFFSET, _Y_TF_OFFSET, self._tf_z_rad, 0.0, 2.0 * pi)
        context.fill()

        return True

    def key_press_event(self, widget, event):
        self._ft_state.exit_on_trigger(event)
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

    def register_callbacks(self, window):
        window.connect('key-press-event', self.key_press_event)
        window.add_events(gtk.gdk.KEY_PRESS_MASK)


class SynClient:

    def __init__(self, test):
        self._test = test
        proc = subprocess.Popen(_SYNCLIENT_SETTINGS_CMDLINE.split(),
                                stdout=subprocess.PIPE)
        settings_data = proc.stdout.readlines()
        settings = {}
        for line in settings_data:
            cols = [x for x in line.rstrip().split(' ') if x]
            if len(cols) != 3 or cols[1] != '=':
                continue
            settings[cols[0]] = cols[2]
        self._xmin = float(settings['LeftEdge'])
        self._xmax = float(settings['RightEdge'])
        self._ymin = float(settings['TopEdge'])
        self._ymax = float(settings['BottomEdge'])
        self._zmin = float(settings['FingerLow'])
        self._zmax = float(settings['FingerHigh'])
        self._proc = subprocess.Popen(_SYNCLIENT_CMDLINE.split(),
                                      stdout=subprocess.PIPE)
        gobject.io_add_watch(self._proc.stdout, gobject.IO_IN, self.recv)

    def recv(self, src, cond):
        data = self._proc.stdout.readline().split()
        if len(data) != 17:
            factory.log('unknown data : %d, %s' % (len(data), data))
            return True
        if data[0] == 'time':
            return True
        data_x, data_y, data_z, f, w, l, r = data[1:8]
        x = sorted([self._xmin, float(data_x), self._xmax])[1]
        x = (x - self._xmin) / (self._xmax - self._xmin)
        y = sorted([self._ymin, float(data_y), self._ymax])[1]
        y = (y - self._ymin) / (self._ymax - self._ymin)
        z = sorted([self._zmin, float(data_z), self._zmax])[1]
        z = (z - self._zmin) / (self._zmax - self._zmin)
        self._test.device_event(x, y, z, int(f), int(l), int(r))
        return True

    def quit(self):
        factory.log('killing SynClient ...')
        self._proc.kill()
        factory.log('dead')


class factory_Touchpad(test.test):
    version = 1
    preserve_srcdir = True

    def run_once(self,
                 test_widget_size=None,
                 trigger_set=None,
                 result_file_path=None):

        factory.log('%s run_once' % self.__class__)

        ft_state = ful.State(
            trigger_set=trigger_set,
            result_file_path=result_file_path)

        os.chdir(self.srcdir)
        tp_image = cairo.ImageSurface.create_from_png('touchpad.png')
        image_size = (tp_image.get_width(), tp_image.get_height())

        drawing_area = gtk.DrawingArea()

        test = TouchpadTest(tp_image, drawing_area, ft_state)

        drawing_area.set_size_request(*image_size)
        drawing_area.connect('expose_event', test.expose_event)
        drawing_area.connect('button-press-event', test.button_press_event)
        drawing_area.connect('button-release-event', test.button_release_event)
        drawing_area.connect('motion-notify-event', test.motion_event)
        drawing_area.add_events(gtk.gdk.EXPOSURE_MASK |
                                gtk.gdk.BUTTON_PRESS_MASK |
                                gtk.gdk.BUTTON_RELEASE_MASK |
                                gtk.gdk.POINTER_MOTION_MASK)

        synclient = SynClient(test)

        ft_state.run_test_widget(
            test_widget=drawing_area,
            test_widget_size=test_widget_size,
            window_registration_callback=test.register_callbacks,
            cleanup_callback=synclient.quit)

        factory.log('%s run_once finished' % self.__class__)
