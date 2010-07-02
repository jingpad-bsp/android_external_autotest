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
# _result_file_path.


from autotest_lib.client.bin import factory
from autotest_lib.client.common_lib import error

import gtk
import sys


BLACK = gtk.gdk.Color()
RED =   gtk.gdk.Color(0xFFFF, 0, 0)
GREEN = gtk.gdk.Color(0, 0xFFFF, 0)
BLUE =  gtk.gdk.Color(0, 0, 0xFFFF)
WHITE = gtk.gdk.Color(0xFFFF, 0xFFFF, 0xFFFF)

LIGHT_GREEN = gtk.gdk.color_parse('light green')

ACTIVE = 'ACTIVE'
PASSED = 'PASS'
FAILED = 'FAIL'
UNTESTED = 'UNTESTED'

STATUS_CODE_MAP = {
    'START': ACTIVE,
    'GOOD': PASSED,
    'FAIL': FAILED,
    'ERROR': FAILED}

LABEL_COLORS = {
    ACTIVE: gtk.gdk.color_parse('light goldenrod'),
    PASSED: gtk.gdk.color_parse('pale green'),
    FAILED: gtk.gdk.color_parse('tomato'),
    UNTESTED: gtk.gdk.color_parse('dark slate grey')}


class State:

    def __init__(self, trigger_set=set(), result_file_path=None):
        self._got_trigger = None
        self._result_file_path = result_file_path
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
            pixmap = gtk.gdk.Pixmap(None, 1, 1, 1)
            color = gtk.gdk.Color()
            cursor = gtk.gdk.Cursor(pixmap, pixmap, color, color, 0, 0)
            window.window.set_cursor(cursor)

        if window_registration_callback is not None:
            window_registration_callback(window)

        factory.log('factory_test running gtk.main')
        gtk.main()
        factory.log('factory_test quit gtk.main')

        if cleanup_callback is not None:
            cleanup_callback()

        gtk.gdk.pointer_ungrab()
        gtk.gdk.keyboard_ungrab()

        if self._got_trigger is None:
            return
        with open(self._result_file_path, 'w') as file:
            file.write('%s\n' % repr(self._got_trigger))
        raise error.TestFail('explicit test switch triggered (%s)' %
                             self._got_trigger)
