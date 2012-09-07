# -*- coding: utf-8 -*-
#
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This is a factory test to test the LCD display.


import gtk
import pango
import os
import re
import sys

from gtk import gdk

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import factory
from cros.factory.test import ui as ful


_LABEL_SIZE = (180, 30)
_LABEL_UNTESTED_FG = gtk.gdk.color_parse('grey40')

_MESSAGE_STR = ('hold SPACE to display pattern,\n' +
                'hit TAB to fail and ENTER to pass\n' +
                '压住空白键以显示检查用的图样,\n' +
                '错误请按 TAB，成功请按 ENTER\n')


def pattern_cb_solid(widget, event, color=None):
    dr = widget.window
    xmax, ymax = dr.get_size()
    gc = gtk.gdk.GC(dr)
    gc.set_rgb_fg_color(color)
    dr.draw_rectangle(gc, True, 0, 0, xmax, ymax)
    return False


def pattern_cb_grid(widget, event, color=None):
    dr = widget.window
    xmax, ymax = dr.get_size()
    gc = gtk.gdk.GC(dr)
    gc.set_rgb_fg_color(ful.BLACK)
    dr.draw_rectangle(gc, True, 0, 0, xmax, ymax)
    gc.set_rgb_fg_color(color)
    gc.set_line_attributes(1,
                           gtk.gdk.LINE_SOLID,
                           gtk.gdk.CAP_BUTT,
                           gtk.gdk.JOIN_MITER)
    for x in range(0, xmax - 1, 20):
        dr.draw_line(gc, x, 0, x, ymax)
    for y in range(0, ymax - 1, 20):
        dr.draw_line(gc, 0, y, xmax, y)
    dr.draw_line(gc, xmax - 1, 0, xmax - 1, ymax)
    dr.draw_line(gc, xmax, ymax - 1, 0, ymax - 1)
    return False


def pattern_vgrad(widget, event, level_list, color=None):
    dr = widget.window
    xmax, ymax = dr.get_size()
    gc = gtk.gdk.GC(dr)
    red = green = blue = 0
    num_levels = len(level_list)
    for i, level in enumerate(level_list):
        ystart = (ymax * i) / num_levels
        yend = ((ymax * (i+1)) / num_levels)
        for x in range(0, xmax - 1, xmax / level):
            i = 65535 / xmax * x
            if color == ful.RED:
                red = i
            elif color == ful.GREEN:
                green = i
            elif color == ful.BLUE:
                blue = i
            else:
                red = green = blue = i
            gc.set_rgb_fg_color(gtk.gdk.Color(red, green, blue))
            dr.draw_rectangle(gc, True, x, ystart, x + xmax / level, yend)
    return False


def pattern_full_rect(widget, event):
    dr = widget.window
    xmax, ymax = dr.get_size()
    gc = gtk.gdk.GC(dr)
    gc.set_rgb_fg_color(ful.BLACK)
    dr.draw_rectangle(gc, True, 0, 0, xmax, ymax)
    gc.set_rgb_fg_color(ful.WHITE)
    gc.set_line_attributes(1,
                           gtk.gdk.LINE_SOLID,
                           gtk.gdk.CAP_BUTT,
                           gtk.gdk.JOIN_MITER)
    dr.draw_line(gc, 0, 0, xmax, 0)
    dr.draw_line(gc, xmax - 1, 0, xmax - 1, ymax)
    dr.draw_line(gc, xmax, ymax - 1, 0, ymax - 1)
    dr.draw_line(gc, 0, ymax, 0, 0)
    return False

_GRAD_LEVELS = [ 16, 64, 256 ]

_PATTERN_LIST = [
    ('solid red', lambda *x: pattern_cb_solid(*x, **{'color':ful.RED})),
    ('solid green', lambda *x: pattern_cb_solid(*x, **{'color':ful.GREEN})),
    ('solid blue', lambda *x: pattern_cb_solid(*x, **{'color':ful.BLUE})),
    ('solid white', lambda *x: pattern_cb_solid(*x, **{'color':ful.WHITE})),
    ('solid gray', lambda *x: pattern_cb_solid(*x,
                   **{'color':gtk.gdk.Color(65535 / 2, 65525 / 2, 65535 / 2)})),
    ('solid black', lambda *x: pattern_cb_solid(*x, **{'color':ful.BLACK})),
    ('grid', lambda *x: pattern_cb_grid(*x, **{'color':ful.WHITE})),
    ('rectangle', lambda *x: pattern_full_rect(*x)),
    ('grad red', lambda *x: pattern_vgrad(*x, **{'level_list':_GRAD_LEVELS,
                                                 'color':ful.RED})),
    ('grad green', lambda *x: pattern_vgrad(*x,
                                            **{'level_list':_GRAD_LEVELS,
                                               'color':ful.GREEN})),
    ('grad blue', lambda *x: pattern_vgrad(*x,
                                           **{'level_list':_GRAD_LEVELS,
                                              'color':ful.BLUE})),
    ('grad white', lambda *x: pattern_vgrad(*x,
                                            **{'level_list':_GRAD_LEVELS,
                                               'color':ful.WHITE}))]


class factory_Display(test.test):
    version = 2

    def display_full_screen(self, pattern_callback):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        screen = window.get_screen()
        screen_size = (screen.get_width(), screen.get_height())
        window.set_size_request(*screen_size)
        drawing_area = gtk.DrawingArea()
        window.add(drawing_area)
        window.show_all()
        self._fs_window = window
        self.register_callbacks(self._fs_window)
        drawing_area.connect('expose_event', pattern_callback)

    def goto_next_pattern(self):
        if not self._pattern_queue:
            gtk.main_quit()
            return
        self._current_pattern = self._pattern_queue.pop()
        name, cb_fn = self._current_pattern
        self.update_status(name, ful.ACTIVE)
        self._current_pattern_shown = False

    def key_press_callback(self, widget, event):
        pattern_name, pattern_cb = self._current_pattern
        if event.keyval == gtk.keysyms.space and not self._fs_window:
            self.display_full_screen(pattern_cb)
        return True

    def key_release_callback(self, widget, event):
        pattern_name, pattern_cb = self._current_pattern
        if event.keyval == gtk.keysyms.space and self._fs_window is not None:
            self._fs_window.destroy()
            self._fs_window = None
            self._current_pattern_shown = True
        elif event.keyval == gtk.keysyms.Tab and self._current_pattern_shown:
            self.update_status(pattern_name, ful.FAILED)
            self.goto_next_pattern()
        elif event.keyval == gtk.keysyms.Return and self._current_pattern_shown:
            self.update_status(pattern_name, ful.PASSED)
            self.goto_next_pattern()
        elif event.keyval == ord('Q'):
            gtk.main_quit()
        self._test_widget.queue_draw()
        return True

    def update_status(self, name, status):
        self._status_map[name] = status
        self._label_status[name].set_text(status)
        self._label_status[name].modify_fg(gtk.STATE_NORMAL,
                                           ful.LABEL_COLORS[status])
        self._label_status[name].queue_draw()

    def make_pattern_label_box(self, name):

        label_status = ful.make_label(
            ful.UNTESTED, size=_LABEL_SIZE,
            alignment=(0, 0.5), fg=_LABEL_UNTESTED_FG)
        self._label_status[name] = label_status

        label_en = ful.make_label(name, size=_LABEL_SIZE, alignment=(1, 0.5))
        label_sep = ful.make_label(' : ', alignment=(0.5, 0.5))

        hbox = gtk.HBox()
        hbox.pack_end(label_status, False, False)
        hbox.pack_end(label_sep, False, False)
        hbox.pack_end(label_en, False, False)

        eb = gtk.EventBox()
        eb.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        eb.add(hbox)
        return eb

    def register_callbacks(self, window):
        window.connect('key-press-event', self.key_press_callback)
        window.add_events(gdk.KEY_PRESS_MASK)
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gdk.KEY_RELEASE_MASK)

    def run_once(self, regex_filter=None):
        global _PATTERN_LIST
        '''
        Args:
            regex_filter: optional regular expression to select patterns.
        '''

        factory.log('%s run_once' % self.__class__)
        if regex_filter is not None:
            _PATTERN_LIST = [x for x in _PATTERN_LIST
                             if re.search(regex_filter, x[0])]

        self._pattern_queue = [x for x in reversed(_PATTERN_LIST)]
        self._status_map = dict((n, ful.UNTESTED) for n, f in _PATTERN_LIST)
        self._label_status = dict()

        self._prompt_label = ful.make_label(_MESSAGE_STR, alignment=(0.5, 0.5))

        vbox = gtk.VBox()
        vbox.pack_start(self._prompt_label, False, False)

        for name, cb_fun in _PATTERN_LIST:
            label_box = self.make_pattern_label_box(name)
            vbox.pack_start(label_box, False, False)

        test_widget = gtk.EventBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        test_widget.add(vbox)
        self._test_widget = test_widget

        self.goto_next_pattern()

        self._fs_window = None

        ful.run_test_widget(self.job, test_widget,
            window_registration_callback=self.register_callbacks)

        failed_set = set(name for name, status in self._status_map.items()
                         if status is not ful.PASSED)
        if failed_set:
            raise error.TestFail('some patterns failed\n' \
                                 '以下图样测试未通过: %s' %
                                 ', '.join(failed_set))

        factory.log('%s run_once finished' % self.__class__)
