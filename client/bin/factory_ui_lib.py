# -*- coding: utf-8 -*-
#
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This library provides convenience routines to launch factory tests.
# This includes support for drawing the test widget in a window at the
# proper location, grabbing control of the mouse, and making the mouse
# cursor disappear.


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

SEP_COLOR = gtk.gdk.color_parse('grey50')

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


def make_hsep(width=1):
    frame = gtk.EventBox()
    frame.set_size_request(-1, width)
    frame.modify_bg(gtk.STATE_NORMAL, SEP_COLOR)
    return frame


def make_vsep(width=1):
    frame = gtk.EventBox()
    frame.set_size_request(width, -1)
    frame.modify_bg(gtk.STATE_NORMAL, SEP_COLOR)
    return frame


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


def run_test_widget(job, test_widget,
                    invisible_cursor=True,
                    window_registration_callback=None,
                    cleanup_callback=None):

    test_widget_size = job.factory_shared_dict.get('test_widget_size')

    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    window.modify_bg(gtk.STATE_NORMAL, BLACK)
    window.set_size_request(*test_widget_size)

    align = gtk.Alignment(xalign=0.5, yalign=0.5)
    align.add(test_widget)

    window.add(align)
    window.show_all()

    if window_registration_callback is not None:
        window_registration_callback(window)

    gtk.gdk.pointer_grab(window.window, confine_to=window.window)

    if invisible_cursor:
        hide_cursor(window.window)

    gtk.main()

    gtk.gdk.pointer_ungrab()

    if cleanup_callback is not None:
        cleanup_callback()
