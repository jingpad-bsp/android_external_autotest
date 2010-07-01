# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This is an example factory test that does not really do anything --
# it displays a message in the center of the testing area, as
# communicated by arguments to run_once().  This test makes use of the
# factory_test library to display its UI, and to monitor keyboard
# events for test-switching triggers.  This test can be terminated by
# typing SHIFT-Q.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import factory_test

import gtk
import pango
import os
import sys


def XXX_log(s):
    print >> sys.stderr, 'FACTORY: ' + s


_BLACK = gtk.gdk.Color()
_RED =   gtk.gdk.Color(0xFFFF, 0, 0)
_GREEN = gtk.gdk.Color(0, 0xFFFF, 0)
_BLUE =  gtk.gdk.Color(0, 0, 0xFFFF)
_WHITE = gtk.gdk.Color(0xFFFF, 0xFFFF, 0xFFFF)

_ACTIVE = 'ACTIVE'
_PASSED = 'PASS'
_FAILED = 'FAIL'
_UNTESTED = 'UNTESTED'

_LABEL_COLORS = {
    _ACTIVE: gtk.gdk.color_parse('light goldenrod'),
    _PASSED: gtk.gdk.color_parse('pale green'),
    _FAILED: gtk.gdk.color_parse('tomato'),
    _UNTESTED: gtk.gdk.color_parse('dark slate grey')}

_LABEL_STATUS_SIZE = (140, 30)
_LABEL_STATUS_FONT = pango.FontDescription('courier new condensed 16')
_LABEL_FONT = pango.FontDescription('courier new condensed 20')
_LABEL_FG = gtk.gdk.color_parse('light green')
_LABEL_UNTESTED_FG = gtk.gdk.color_parse('grey40')


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
    gc.set_rgb_fg_color(_BLACK)
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
    ('solid red', lambda *x: pattern_cb_solid(*x, **{'color':_RED})),
    ('solid green', lambda *x: pattern_cb_solid(*x, **{'color':_GREEN})),
    ('solid blue', lambda *x: pattern_cb_solid(*x, **{'color':_BLUE})),
    ('solid white', lambda *x: pattern_cb_solid(*x, **{'color':_WHITE})),
    ('grid', lambda *x: pattern_cb_grid(*x, **{'color':_GREEN}))]


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
        self._status_map[name] = _ACTIVE
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
            self._status_map[pattern_name] = _FAILED
            self.goto_next_pattern()
        elif event.keyval == gtk.keysyms.Return and self._current_pattern_shown:
            self._status_map[pattern_name] = _PASSED
            self.goto_next_pattern()
        elif event.keyval == ord('Q'):
            factory_test.XXX_log('factory_Display exiting...')
            gtk.main_quit()
        else:
            factory_test.test_switch_on_trigger(event)
        self._test_widget.queue_draw()
        return True

    def label_status_expose(self, widget, event, name=None):
        status = self._status_map[name]
        widget.set_text(status)
        widget.modify_fg(gtk.STATE_NORMAL, _LABEL_COLORS[status])

    def make_pattern_label_box(self, name):
        eb = gtk.EventBox()
        eb.modify_bg(gtk.STATE_NORMAL, _BLACK)
        label_status = gtk.Label(_UNTESTED)
        label_status.set_size_request(*_LABEL_STATUS_SIZE)
        label_status.set_alignment(0, 0.5)
        label_status.modify_font(_LABEL_STATUS_FONT)
        label_status.modify_fg(gtk.STATE_NORMAL, _LABEL_UNTESTED_FG)
        expose_cb = lambda *x: self.label_status_expose(*x, **{'name':name})
        label_status.connect('expose_event', expose_cb)
        label_en = gtk.Label(name)
        label_en.set_alignment(1, 0.5)
        label_en.modify_font(_LABEL_STATUS_FONT)
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

    def register_callbacks(self, window):
        window.connect('key-press-event', self.key_press_callback)
        window.add_events(gtk.gdk.KEY_PRESS_MASK)
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gtk.gdk.KEY_RELEASE_MASK)

    def run_once(self, test_widget_size=None, trigger_set=None,
                 result_file_path=None):

        factory_test.XXX_log('factory_Display')

        xset_status = os.system('xset r off')
        xmm_status = os.system('xmodmap -e "clear Lock"')
        if xset_status or xmm_status:
            raise TestFail('ERROR: disabling key repeat or caps lock')

        factory_test.init(trigger_set=trigger_set,
                          result_file_path=result_file_path)

        self._pattern_queue = [x for x in reversed(_PATTERN_LIST)]
        self._status_map = dict((n, _UNTESTED) for n, f in _PATTERN_LIST)

        prompt_label = gtk.Label('hold SPACE to display pattern,\n'
                                 'TAB to fail and RETURN to pass\n')
        prompt_label.modify_font(_LABEL_FONT)
        prompt_label.set_alignment(0.5, 0.5)
        prompt_label.modify_fg(gtk.STATE_NORMAL, _LABEL_FG)
        self._prompt_label = prompt_label

        vbox = gtk.VBox()
        vbox.pack_start(prompt_label, False, False)

        for name, cb_fun in _PATTERN_LIST:
            label_box = self.make_pattern_label_box(name)
            vbox.pack_start(label_box, False, False)

        test_widget = gtk.EventBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
        test_widget.add(vbox)
        self._test_widget = test_widget

        self.goto_next_pattern()

        self._fs_window = None

        factory_test.run_test_widget(
            test_widget=test_widget,
            test_widget_size=test_widget_size,
            window_registration_callback=self.register_callbacks)

        failed_set = set(name for name, status in self._status_map.items()
                         if status is not _PASSED)
        if failed_set:
            raise error.TestFail('some patterns failed (%s)' %
                                 ', '.join(failed_set))

        factory_test.XXX_log('exiting factory_Display')
