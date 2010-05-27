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


from autotest_lib.client.common_lib import error

import gtk
import sys


def XXX_log(s):
    print >> sys.stderr, '--- XXX : ' + s


_BLACK = gtk.gdk.color_parse('black')


_got_trigger = None
_trigger_set = None
_result_file_path = None


def init(trigger_set=set(), result_file_path=None):
    global _trigger_set, _result_file_path
    _result_file_path = result_file_path
    _trigger_set = [ord(x) for x in trigger_set]


def test_switch_on_trigger(event):
    char = event.keyval in range(32,127) and chr(event.keyval) or None
    global _trigger_set, _result_file_path, _got_trigger
    if ('GDK_CONTROL_MASK' not in event.state.value_names
        or event.keyval not in _trigger_set):
        return False
    XXX_log('got test switch trigger %s(%s)' % (event.keyval, char))
    _got_trigger = char
    gtk.main_quit()
    return True


def run_test_widget(test_widget=None, test_widget_size=None,
                    window_registration_callback=None):
    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    window.connect('destroy', lambda _: gtk.main_quit())
    window.modify_bg(gtk.STATE_NORMAL, _BLACK)
    window.set_size_request(*test_widget_size)

    align = gtk.Alignment(xalign=0.5, yalign=0.5)
    align.add(test_widget)

    window.add(align)
    window.show_all()

    gtk.gdk.pointer_grab(window.window, confine_to=window.window)
    gtk.gdk.keyboard_grab(window.window)

    # create and use an invisible cursor
    pixmap = gtk.gdk.Pixmap(None, 1, 1, 1)
    color = gtk.gdk.Color()
    cursor = gtk.gdk.Cursor(pixmap, pixmap, color, color, 0, 0)
    window.window.set_cursor(cursor)

    if window_registration_callback is not None:
        window_registration_callback(window)

    XXX_log('factory_test running gtk.main')
    gtk.main()
    XXX_log('factory_test quit gtk.main')

    gtk.gdk.pointer_ungrab()
    gtk.gdk.keyboard_ungrab()

    global _got_trigger
    if _got_trigger is None:
        return
    with open(_result_file_path, 'w') as file:
        file.write('%s\n' % repr(_got_trigger))
    raise error.TestFail('explicit test switch triggered (%s)' % _got_trigger)
