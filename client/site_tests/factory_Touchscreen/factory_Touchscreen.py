# -*- coding: utf-8 -*-
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# Intended for use during manufacturing to validate that the touchscreen
# is functioning properly.

import cairo
import gobject
import gtk
import os

from glob import glob
from gtk import gdk

from autotest_lib.client.bin import test
from autotest_lib.client.bin.input.input_device import *
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import factory
from cros.factory.test import ui as ful


_X_SEGMENTS = 15
_Y_SEGMENTS = 12

_X_TS_OFFSET = 12
_Y_TS_OFFSET = 12
_TS_WIDTH = 756
_TS_HEIGHT = 416
_TS_SECTOR_WIDTH = (_TS_WIDTH / _X_SEGMENTS) - 1
_TS_SECTOR_HEIGHT = (_TS_HEIGHT / _Y_SEGMENTS) - 1

_F_RADIUS = 21


class TouchscreenTest:

    def __init__(self, tp_image, drawing_area):
        self._tp_image = tp_image
        self._drawing_area = drawing_area
        self._motion_grid = {}
        for x in range(_X_SEGMENTS):
            for y in range(_Y_SEGMENTS):
                self._motion_grid['%d,%d' % (x, y)] = False
        self._of_z_rad = 0
        self._tf_z_rad = 0

        self._current_x = None
        self._current_y = None

    def calc_missing_string(self):
        missing = []
        missing_motion_sectors = sorted(
            i for i, v in self._motion_grid.items() if v is False)
        if missing_motion_sectors:
            missing.append('Missing following motion sectors\n'
                    '未侦测到下列位置的触控移动讯号 [%s]' %
                    ', '.join(missing_motion_sectors))
        return '\n'.join(missing)

    def device_event(self, x, y, z, fingers):
        x_seg = int(round(x / (1.0 / float(_X_SEGMENTS - 1))))
        y_seg = int(round(y / (1.0 / float(_Y_SEGMENTS - 1))))
        z_rad = int(round(z / (1.0 / float(_F_RADIUS - 1))))

        index = '%d,%d' % (x_seg, y_seg)
        self._current_x = x_seg
        self._current_y = y_seg

        self._of_z_rad = z_rad
        self._tf_z_rad = z_rad

        assert(index in self._motion_grid)

        if fingers == 1 and not self._motion_grid[index]:
            self._motion_grid[index] = True

        self._drawing_area.queue_draw()

        if not self.calc_missing_string():
            factory.log('completed successfully')
            gtk.main_quit()

    def expose_event(self, widget, event):
        context = widget.window.cairo_create()

        # Fill context with factory UI default background color.
        context.set_source_rgb(0, 0, 0)
        context.paint()

        # Show touchscreen image as the background.
        context.set_source_surface(self._tp_image, 0, 0)
        context.paint()

        context.set_source_rgba(*ful.RGBA_GREEN_OVERLAY)

        for index in self._motion_grid:
            if not self._motion_grid[index]:
                continue
            ind_x, ind_y = map(int, index.split(','))
            x = _X_TS_OFFSET + (ind_x * (_TS_SECTOR_WIDTH + 1))
            y = _Y_TS_OFFSET + (ind_y * (_TS_SECTOR_HEIGHT + 1))
            coords = (x, y, _TS_SECTOR_WIDTH, _TS_SECTOR_HEIGHT)
            context.rectangle(*coords)
            context.fill()

        if self._current_x is not None:
            context.set_source_rgba(*ful.RGBA_RED_OVERLAY)
            coords = (_X_TS_OFFSET + (self._current_x * (_TS_SECTOR_WIDTH + 1)),
                    _Y_TS_OFFSET + (self._current_y * (_TS_SECTOR_HEIGHT + 1)),
                    _TS_SECTOR_WIDTH, _TS_SECTOR_HEIGHT)
            context.rectangle(*coords)
            context.fill()

        return True

class EvdevTouchscreen:

    def __init__(self, test, device):
        self._test = test
        self.ev = InputEvent()
        self.device = device

        self._xmin = device.get_x_min()
        self._xmax = device.get_x_max()
        self._ymin = device.get_y_min()
        self._ymax = device.get_y_max()
        self._zmin = device.get_pressure_min()
        self._zmax = device.get_pressure_max()

        factory.log('x:(%d : %d), y:(%d : %d), z:(%d, %d)' %
                    (self._xmin, self._xmax, self._ymin, self._ymax,
                     self._zmin, self._zmax))
        gobject.io_add_watch(device.f, gobject.IO_IN, self.recv)

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

        # Convert raw coordinate to % of range.
        x_pct = self._to_percent(x, self._xmin, self._xmax)
        y_pct = self._to_percent(y, self._ymin, self._ymax)
        z_pct = self._to_percent(z, self._zmin, self._zmax)

        factory.log('x=%f y=%f z=%f f=%d' %
                    (x_pct, y_pct, z_pct, f))

        self._test.device_event(x_pct, y_pct, z_pct, f)
        return True

    def quit(self):
        if self.device and self.device.f and not self.device.f.closed:
            factory.log('Closing %s...' % self.device.path)
            self.device.f.close()


class factory_Touchscreen(test.test):
    version = 1
    preserve_srcdir = True

    def run_once(self):

        factory.log('%s run_once' % self.__class__)

        os.chdir(self.srcdir)
        tp_image = cairo.ImageSurface.create_from_png('touchscreen.png')
        image_size = (tp_image.get_width(), tp_image.get_height())

        drawing_area = gtk.DrawingArea()

        test = TouchscreenTest(tp_image, drawing_area)

        drawing_area.set_size_request(*image_size)
        drawing_area.connect('expose_event', test.expose_event)
        drawing_area.add_events(gdk.EXPOSURE_MASK)

        test_widget = gtk.VBox()
        test_widget.set_spacing(20)
        test_widget.pack_start(drawing_area, False, False)
        usage_label = ful.make_label(
                'Move one finger across entire touchscreen surface\n')
        test_widget.pack_start(usage_label, False, False)

        # Detect an evdev compatible touchscreen device.
        # TODO(djkurtz): Use gudev to detect touchscreen
        for evdev in glob('/dev/input/event*'):
            device = InputDevice(evdev)
            if device.is_touchscreen():
                # Using EvdevTouchscreen if an evdev compatible touchscreen
                # device is found.
                factory.log('EvdevTouchscreen: using %s,  device %s' %
                            (device.name, device.path))
                touchscreen = EvdevTouchscreen(test, device)
                break
        else:
            raise error.TestFail('No compatible touchscreen device is found\n')

        self._current_x = None
        self._current_y = None

        ful.run_test_widget(self.job, test_widget,
                cleanup_callback=touchscreen.quit)

        missing = test.calc_missing_string()
        if missing:
            raise error.TestFail(missing)

        factory.log('%s run_once finished' % self.__class__)
