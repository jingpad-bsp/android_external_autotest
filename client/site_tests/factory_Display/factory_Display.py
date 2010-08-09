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
import sys

from gtk import gdk

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


_LABEL_SIZE = (180, 30)
_LABEL_UNTESTED_FG = gtk.gdk.color_parse('grey40')

_MESSAGE_STR = ('hold SPACE to display pattern,\n' +
                'hit TAB to fail and ENTER to pass\n' +
                '壓住空白鍵以顯示檢查用的圖樣,\n' +
                '錯誤請按 TAB，成功請按 ENTER\n')


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
    for x in range(0, xmax, 20):
        dr.draw_line(gc, x, 0, x, ymax)
    for y in range(0, ymax, 20):
        dr.draw_line(gc, 0, y, xmax, y)
    return False


_PATTERN_LIST = [
    ('solid red', lambda *x: pattern_cb_solid(*x, **{'color':ful.RED})),
    ('solid green', lambda *x: pattern_cb_solid(*x, **{'color':ful.GREEN})),
    ('solid blue', lambda *x: pattern_cb_solid(*x, **{'color':ful.BLUE})),
    ('solid white', lambda *x: pattern_cb_solid(*x, **{'color':ful.WHITE})),
    ('grid', lambda *x: pattern_cb_grid(*x, **{'color':ful.GREEN}))]


class factory_Display(test.test):
    version = 1

    def display_full_screen(self, pattern_callback):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        screen = window.get_screen()
        screen_size = (screen.get_width(), screen.get_height())
        window.set_size_request(*screen_size)
        drawing_area = gtk.DrawingArea()
        window.add(drawing_area)
        window.show_all()
        self._fs_window = window
        drawing_area.connect('expose_event', pattern_callback)

    def goto_next_pattern(self):
        if not self._pattern_queue:
            gtk.main_quit()
            return
        self._current_pattern = self._pattern_queue.pop()
        name, cb_fn = self._current_pattern
        self._status_map[name] = ful.ACTIVE
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
            self._status_map[pattern_name] = ful.FAILED
            self.goto_next_pattern()
        elif event.keyval == gtk.keysyms.Return and self._current_pattern_shown:
            self._status_map[pattern_name] = ful.PASSED
            self.goto_next_pattern()
        elif event.keyval == ord('Q'):
            gtk.main_quit()
        else:
            self._ft_state.exit_on_trigger(event)
        self._test_widget.queue_draw()
        return True

    def label_status_expose(self, widget, event, name=None):
        status = self._status_map[name]
        widget.set_text(status)
        widget.modify_fg(gtk.STATE_NORMAL, ful.LABEL_COLORS[status])

    def make_pattern_label_box(self, name):

        label_status = ful.make_label(
            ful.UNTESTED, size=_LABEL_SIZE,
            alignment=(0, 0.5), fg=_LABEL_UNTESTED_FG)
        expose_cb = lambda *x: self.label_status_expose(*x, **{'name':name})
        label_status.connect('expose_event', expose_cb)

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

    def run_once(self,
                 test_widget_size=None,
                 trigger_set=None):

        factory.log('%s run_once' % self.__class__)

        self._ft_state = ful.State(trigger_set)

        self._pattern_queue = [x for x in reversed(_PATTERN_LIST)]
        self._status_map = dict((n, ful.UNTESTED) for n, f in _PATTERN_LIST)

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

        self._ft_state.run_test_widget(
            test_widget=test_widget,
            test_widget_size=test_widget_size,
            window_registration_callback=self.register_callbacks)

        failed_set = set(name for name, status in self._status_map.items()
                         if status is not ful.PASSED)
        if failed_set:
            raise error.TestFail('some patterns failed\n' \
                                 '以下圖樣測試未通過: %s' %
                                 ', '.join(failed_set))

        factory.log('%s run_once finished' % self.__class__)
