# -*- coding: utf-8 -*-
#
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This is a factory test to test the LEDs (wifi, battery, etc).


import cairo
import gtk
import pango
import os
import subprocess
import sys
import re

from cmath import pi
from gtk import gdk

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.bin import factory_error as error


_LABEL_STATUS_SIZE = (140, 30)
_LABEL_FONT = pango.FontDescription('courier new condensed 16')
_LABEL_FG = gtk.gdk.color_parse('light green')
_LABEL_UNTESTED_FG = gtk.gdk.color_parse('grey40')

_PATTERN_LABEL_STR = 'pattern / 圖樣: '

_ORANGE = gtk.gdk.color_parse('orange')

_LED_NAMES = 'sleepled battchgled wlan battfulled powerled 3g'.split()
_ORANGE_LED_NAMES = _LED_NAMES[0:3]
_BLUE_LED_NAMES = _LED_NAMES[3:]

_LED_COUNT = 3
_LED_Y_OFFSET = 10
_LED_X_OFFSETS = [10, 80, 150]
_LED_RADIUS = 18
_SHFL_XYR = {'x':166,'y':20, 'r':9}


def run_led_ctl(led_ctl_path, args):
    rc = subprocess.call([led_ctl_path] + args.split())
    if rc != 1:
        factory.log('%s(%s) failed with rc %s' % (led_ctl_path, args, rc))


def pattern_all_off(led_ctl_fn):
    for n in _LED_NAMES:
        led_ctl_fn('-%s -off' % n)
    return [ful.BLACK, ful.BLACK, ful.BLACK]

def pattern_blue_on(led_ctl_fn):
    pattern_all_off(led_ctl_fn)
    for n in _BLUE_LED_NAMES:
        led_ctl_fn('-%s -on' % n)
    return [ful.BLUE, ful.BLUE, ful.BLUE]

def pattern_orange_on(led_ctl_fn):
    pattern_all_off(led_ctl_fn)
    for n in _ORANGE_LED_NAMES:
        led_ctl_fn('-%s -on' % n)
    return [_ORANGE, _ORANGE, _ORANGE]

_PATTERN_LIST = [
    ('all off', pattern_all_off),
    ('blue on', pattern_blue_on),
    ('orange on', pattern_orange_on),
    ('shift led', False)]


class factory_Leds(test.test):
    version = 1
    preserve_srcdir = True

    def goto_next_pattern(self):
        if not self._pattern_queue:
            gtk.main_quit()
            return
        self._current_pattern, cb_fn = self._pattern_queue.pop()
        self._status_map[self._current_pattern] = ful.ACTIVE
        if cb_fn:
            led_ctl_fn = lambda args: run_led_ctl(self._led_ctl_path, args)
            self._led_colors = cb_fn(led_ctl_fn)
        else:
            self._pattern_da.connect('expose_event', self.shift_led_expose)
        self._pattern_da.queue_draw()

    def shift_led_expose(self, widget, event):
        context = widget.window.cairo_create()
        context.set_source_surface(self._shf_image, 0, 0)
        context.paint()

        if self._shift_cnt is 2:
            if self._shift_color is ful.BLACK:
                self._shift_color = ful.BLUE
            else:
                self._shift_color = ful.BLACK
            self._shift_cnt = 0
        context.set_source_color(self._shift_color)
        context.arc(_SHFL_XYR['x'], _SHFL_XYR['y'], _SHFL_XYR['r'],
                    0.0, 2.0 * pi)
        context.fill()

    def pattern_expose(self, widget, event):
        context = widget.window.cairo_create()
        context.set_source_surface(self._leds_image, 0, 0)
        context.paint()
        for led_index in range(_LED_COUNT):
            color = self._led_colors[led_index]
            x_offset = _LED_X_OFFSETS[led_index] + _LED_RADIUS + 3
            y_offset = _LED_Y_OFFSET + _LED_RADIUS + 3
            context.set_source_color(color)
            context.arc(x_offset, y_offset, _LED_RADIUS, 0.0, 2.0 * pi)
            context.fill()

    def quit(self):
        factory.log('releasing LEDs ...')
        run_led_ctl(self._led_ctl_path, '-ledrelease')

    def label_status_expose(self, widget, event, name=None):
        status = self._status_map[name]
        widget.set_text(status)
        widget.modify_fg(gtk.STATE_NORMAL, ful.LABEL_COLORS[status])

    def make_pattern_label_box(self, name):
        eb = gtk.EventBox()
        eb.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        label_status = gtk.Label(ful.UNTESTED)
        label_status.set_size_request(*_LABEL_STATUS_SIZE)
        label_status.set_alignment(0, 0.5)
        label_status.modify_font(_LABEL_FONT)
        label_status.modify_fg(gtk.STATE_NORMAL, _LABEL_UNTESTED_FG)
        expose_cb = lambda *x: self.label_status_expose(*x, **{'name':name})
        label_status.connect('expose_event', expose_cb)
        label_en = gtk.Label(name)
        label_en.set_alignment(1, 0.5)
        label_en.modify_font(_LABEL_FONT)
        label_en.modify_fg(gtk.STATE_NORMAL, _LABEL_FG)
        label_sep = gtk.Label(' : ')
        label_sep.set_alignment(0.5, 0.5)
        label_sep.modify_font(_LABEL_FONT)
        label_sep.modify_fg(gtk.STATE_NORMAL, _LABEL_FG)
        hbox = gtk.HBox()
        hbox.pack_end(label_status, False, False)
        hbox.pack_end(label_sep, False, False)
        hbox.pack_end(label_en, False, False)
        eb.add(hbox)
        return eb

    def key_release_callback(self, widget, event):
        if event.keyval == gtk.keysyms.Tab:
            self._status_map[self._current_pattern] = ful.FAILED
            self.goto_next_pattern()
        elif event.keyval == gtk.keysyms.Return:
            self._status_map[self._current_pattern] = ful.PASSED
            self.goto_next_pattern()
        elif self._current_pattern.startswith("shift") and \
                event.keyval == gtk.keysyms.Shift_L:
            self._shift_cnt += 1
            self._pattern_da.queue_draw()
        return True

    def register_callbacks(self, window):
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gdk.KEY_RELEASE_MASK)

    def _get_embedded_controller_vendor(self):
        # example output of superiotool:
        #  Found Nuvoton WPCE775x (id=0x05, rev=0x02) at 0x2e
        re_vendor = re.compile(r'Found (\w*)')
        vendor = []
        res = utils.system_output('superiotool', ignore_status=True).split('\n')
        for line in res:
            match = re_vendor.search(line)
            if match:
                vendor.append(match.group(1))
        return vendor

    def run_once(self, led_ctl_path=None):

        factory.log('%s run_once' % self.__class__)

        ec_vendor = self._get_embedded_controller_vendor()
        if len(ec_vendor) == 0:
            raise error.TestNAError('No embedded controller vendor found')
        if 'Nuvoton' not in ec_vendor:
            raise error.TestNAError('Currently not supported embedded controllers: %s' %
                                    ', '.join(ec_vendor))

        self._led_ctl_path = led_ctl_path
        if not os.path.exists(self._led_ctl_path):
            raise error.TestNAError('Command %s does not exist' %
                                    self._led_ctl_path)

        self._shift_color = ful.BLACK
        self._shift_cnt = 0

        os.chdir(self.srcdir)
        try:
            image = cairo.ImageSurface.create_from_png('leds.png')
        except cairo.Error as e:
            raise error.TestNAError('Error while opening leds.png: %s' %
                                    e.message)
        image_size = (image.get_width(), image.get_height())
        self._leds_image = image

        image = cairo.ImageSurface.create_from_png('shf.png')
        self._shf_image = image

        self._pattern_queue = [x for x in reversed(_PATTERN_LIST)]
        self._status_map = dict((n, ful.UNTESTED) for n, f in _PATTERN_LIST)

        pattern_da = gtk.DrawingArea()
        pattern_da.set_size_request(*image_size)
        pattern_da.connect('expose_event', self.pattern_expose)
        self._pattern_da = pattern_da

        pattern_label = ful.make_label(_PATTERN_LABEL_STR)

        pattern_box = gtk.HBox()
        pattern_box.pack_start(pattern_label, False, False)
        pattern_box.pack_start(pattern_da, False, False)

        prompt_label = ful.make_label(ful.USER_PASS_FAIL_SELECT_STR)

        subvbox = gtk.VBox()
        for name, cb_fun in _PATTERN_LIST:
            label_box = self.make_pattern_label_box(name)
            subvbox.pack_start(label_box, False, False)

        vbox = gtk.VBox()
        vbox.set_spacing(20)
        vbox.pack_start(prompt_label, False, False)
        vbox.pack_start(pattern_box, False, False)
        vbox.pack_start(subvbox, False, False)

        test_widget = gtk.EventBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        test_widget.add(vbox)
        self._test_widget = test_widget

        self.goto_next_pattern()

        ful.run_test_widget(self.job, test_widget,
            window_registration_callback=self.register_callbacks,
            cleanup_callback=self.quit)

        failed_set = set(name for name, status in self._status_map.items()
                         if status is not ful.PASSED)
        if failed_set:
            raise error.TestFail('Some patterns failed\n' \
                                 '以下圖樣測試未通過: %s' %
                                 ', '.join(failed_set))

        factory.log('%s run_once finished' % self.__class__)
