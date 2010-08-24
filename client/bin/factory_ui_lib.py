# -*- coding: utf-8 -*-
#
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This library provides convenience routines to launch factory tests.
# This includes support for identifying keyboard test switching
# triggers, grabbing control of the keyboard and mouse, and making the
# mouse cursor disappear.  It also manages communication of any found
# keyboard triggers to the control process, via writing data to
# factory.RESULT_FILE_PATH.


from autotest_lib.client.bin import factory
from autotest_lib.client.common_lib import error

from factory import ACTIVE, PASSED, FAILED, UNTESTED, STATUS_CODE_MAP

import cairo
import gtk
import pango
import sys


BLACK = gtk.gdk.Color()
RED =   gtk.gdk.Color(0xFFFF, 0, 0)
GREEN = gtk.gdk.Color(0, 0xFFFF, 0)
BLUE =  gtk.gdk.Color(0, 0, 0xFFFF)
WHITE = gtk.gdk.Color(0xFFFF, 0xFFFF, 0xFFFF)

LIGHT_GREEN = gtk.gdk.color_parse('light green')

RGBA_GREEN_OVERLAY = (0, 0.5, 0, 0.6)
RGBA_YELLOW_OVERLAY = (0.6, 0.6, 0, 0.6)

LABEL_COLORS = {
    ACTIVE: gtk.gdk.color_parse('light goldenrod'),
    PASSED: gtk.gdk.color_parse('pale green'),
    FAILED: gtk.gdk.color_parse('tomato'),
    UNTESTED: gtk.gdk.color_parse('dark slate grey')}

LABEL_FONT = pango.FontDescription('courier new condensed 16')

FAIL_TIMEOUT = 30

USER_PASS_FAIL_SELECT_STR = (
    'hit TAB to fail and ENTER to pass\n' +
    '錯誤請按 TAB，成功請按 ENTER')


def make_label(message, font=LABEL_FONT, fg=LIGHT_GREEN,
               size=None, alignment=None):
    l = gtk.Label(message)
    l.modify_font(font)
    l.modify_fg(gtk.STATE_NORMAL, fg)
    if size:
        l.set_size_request(*size)
    if alignment:
        l.set_alignment(*alignment)
    return l


def make_countdown_widget():
    title = make_label('time remaining / 剩餘時間: ', alignment=(1, 0.5))
    countdown = make_label('%d' % FAIL_TIMEOUT, alignment=(0, 0.5))
    hbox = gtk.HBox()
    hbox.pack_start(title)
    hbox.pack_start(countdown)
    eb = gtk.EventBox()
    eb.modify_bg(gtk.STATE_NORMAL, BLACK)
    eb.add(hbox)
    return eb, countdown


def hide_cursor(gdk_window):
    pixmap = gtk.gdk.Pixmap(None, 1, 1, 1)
    color = gtk.gdk.Color()
    cursor = gtk.gdk.Cursor(pixmap, pixmap, color, color, 0, 0)
    gdk_window.set_cursor(cursor)


class State:

    def __init__(self, trigger_set=set()):
        self._got_trigger = None
        self._trigger_set = [ord(x) for x in trigger_set]

    def exit_on_trigger(self, event):
        char = event.keyval in range(32,127) and chr(event.keyval) or None
        if ('GDK_CONTROL_MASK' not in event.state.value_names
            or event.keyval not in self._trigger_set):
            return False
        factory.log('got test switch trigger %s(%s)' % (event.keyval, char))
        self._got_trigger = char
        gtk.main_quit()
        return True

    def run_test_widget(self,
                        test_widget=None,
                        test_widget_size=None,
                        invisible_cursor=True,
                        window_registration_callback=None,
                        cleanup_callback=None):

        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.modify_bg(gtk.STATE_NORMAL, BLACK)
        window.set_size_request(*test_widget_size)

        align = gtk.Alignment(xalign=0.5, yalign=0.5)
        align.add(test_widget)

        window.add(align)
        window.show_all()

        gtk.gdk.pointer_grab(window.window, confine_to=window.window)
        gtk.gdk.keyboard_grab(window.window)

        if invisible_cursor:
            hide_cursor(window.window)

        if window_registration_callback is not None:
            window_registration_callback(window)

        factory.log('factory_test running gtk.main')
        gtk.main()
        factory.log('factory_test quit gtk.main')

        if cleanup_callback is not None:
            cleanup_callback()

        gtk.gdk.pointer_ungrab()
        gtk.gdk.keyboard_ungrab()

        if self._got_trigger is not None:
            factory.log('run_test_widget returning kbd_shortcut "%s"' %
                        self._got_trigger)
            factory.log_shared_data('activated_kbd_shortcut', self._got_trigger)
