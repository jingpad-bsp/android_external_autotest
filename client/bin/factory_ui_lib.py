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
        with open(factory.RESULT_FILE_PATH, 'w') as file:
            file.write('%s\n' % repr(self._got_trigger))
        raise error.TestFail('explicit test switch triggered (%s)' %
                             self._got_trigger)


class StatusMap():

    def __init__(self, status_file_path, test_list):
        self._test_queue = [t for t in reversed(test_list)]
        self._as_test_set = set(t for t in test_list if t.automated_seq)
        self._status_map = {}
        for test in test_list:
            test_index = self.index(test.formal_name, test.tag_prefix)
            self._status_map[test_index] = (test, UNTESTED, 0, None, None)
            for subtest in test.automated_seq:
                st_index = self.index(subtest.formal_name, subtest.tag_prefix)
                self._status_map[st_index] = (subtest, UNTESTED, 0, None, None)
        self._status_file_path = status_file_path
        self._status_file_pos = 0
        self.read_new_data()

    def index(self, formal_name, tag_prefix):
        return '%s.%s' % (formal_name, tag_prefix)

    def filter(self, target_status):
        comp = (isinstance(target_status, list) and
                (lambda s: s in target_status) or
                (lambda s: s == target_status))
        return [t for t in self._test_queue if comp(self.lookup_status(t))]

    def next_untested(self):
        remaining = self.filter(UNTESTED)
        factory.log('remaining untested = [%s]' %
                    ', '.join([self.index(t.formal_name, t.tag_prefix)
                               for t in remaining]))
        if not remaining: return None
        return remaining.pop()

    def read_new_data(self):
        with open(self._status_file_path) as file:
            file.seek(self._status_file_pos)
            for line in file:
                cols = line.strip().split('\t') + ['']
                code = cols[0]
                test_id = cols[1]
                if code not in STATUS_CODE_MAP or test_id == '----':
                    continue
                status = STATUS_CODE_MAP[code]
                error = status == FAILED and cols[len(cols) - 2] or None
                factory.log('reading code = %s, test_id = %s, error_msg = "%s"'
                            % (code, test_id, error))
                formal_name, _, tag = test_id.rpartition('.')
                tag_prefix, _, count = tag.rpartition('_')
                self.update(formal_name, tag_prefix, status, int(count), error)
            self._status_file_pos = file.tell()
        map(self.update_as_test, self._as_test_set)
        return True

    def update(self, formal_name, tag_prefix, status, count, error):
        test_index = self.index(formal_name, tag_prefix)
        if test_index not in self._status_map:
            factory.log('ignoring status update (%s) for test %s' %
                        (status, test_index))
            return
        test, old_status, old_count, label, _ = self._status_map[test_index]
        if count < old_count:
            factory.log('ERROR: count regression for %s (%d-%d)' %
                        (test_index, old_count, count))
        if test.repeat_forever and status in [PASSED, FAILED]:
            status = UNTESTED
        if status != old_status:
            factory.log('status change for %s : %s/%s -> %s/%s' %
                        (test_index, old_status, old_count, status, count))
            if label is not None:
                label.update(status)
        self._status_map[test_index] = (test, status, count, label, error)

    def update_as_test(self, test):
        st_status_set = set(map(self.lookup_status, test.automated_seq))
        max_count = max(map(self.lookup_count, test.automated_seq))
        if len(st_status_set) == 1:
            status = st_status_set.pop()
        else:
            status = ACTIVE in st_status_set and ACTIVE or FAILED
        self.update(test.formal_name, test.tag_prefix, status, max_count, None)

    def set_label(self, test, label):
        test_index = self.index(test.formal_name, test.tag_prefix)
        test, status, count, _, error = self._status_map[test_index]
        label.update(status)
        self._status_map[test_index] = test, status, count, label, error

    def lookup_status(self, test):
        test_index = self.index(test.formal_name, test.tag_prefix)
        return self._status_map[test_index][1]

    def lookup_count(self, test):
        test_index = self.index(test.formal_name, test.tag_prefix)
        return self._status_map[test_index][2]

    def lookup_label(self, test):
        test_index = self.index(test.formal_name, test.tag_prefix)
        return self._status_map[test_index][3]

    def lookup_error(self, test):
        test_index = self.index(test.formal_name, test.tag_prefix)
        return self._status_map[test_index][4]
