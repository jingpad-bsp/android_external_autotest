# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This is an example factory test that does not really do anything --
# it displays a message in the center of the testing area, as
# communicated by arguments to run_once().  This test makes use of the
# factory_ui_lib library to display its UI, and to monitor keyboard
# events for test-switching triggers.  This test can be terminated by
# typing SHIFT-Q.


import gtk
import pango
import sys

from gtk import gdk
from itertools import count, izip, product

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test

from factory import AutomatedSequence

N_ROW = 15
LABEL_EN_SIZE = (170, 35)
LABEL_EN_SIZE_2 = (450, 25)
LABEL_EN_FONT = pango.FontDescription('courier new extra-condensed 16')
TAB_BORDER = 20

def trim(text, length):
    if len(text) > length:
        text = text[:length-3] + '...'
    return text

class factory_Review(test.test):
    version = 1

    def make_summary_tab(self, status_map, tests):
        n_test = len(tests)
        N_COL = n_test / N_ROW + (n_test % N_ROW != 0)

        info_box = gtk.HBox()
        info_box.set_spacing(20)
        for status in (ful.ACTIVE, ful.PASSED, ful.FAILED, ful.UNTESTED):
            label = ful.make_label(status,
                                   size=LABEL_EN_SIZE,
                                   font=LABEL_EN_FONT,
                                   alignment=(0.5, 0.5),
                                   fg=ful.LABEL_COLORS[status])
            info_box.pack_start(label, False, False)

        status_table = gtk.Table(N_ROW, N_COL, True)
        for (j, i), (t, p) in izip(product(xrange(N_COL), xrange(N_ROW)),
                                   tests):
            msg_en = t.label_en
            if p is not None:
                msg_en = '  ' + msg_en
            msg_en = trim(msg_en, 12)
            if t.label_zw:
                msg = '{0:<12} ({1})'.format(msg_en, t.label_zw)
            else:
                msg = msg_en
            status = status_map.lookup_status(t)
            status_label = ful.make_label(msg,
                                          size=LABEL_EN_SIZE_2,
                                          font=LABEL_EN_FONT,
                                          alignment=(0.0, 0.5),
                                          fg=ful.LABEL_COLORS[status])
            status_table.attach(status_label, j, j+1, i, i+1)

        vbox = gtk.VBox()
        vbox.set_spacing(20)
        vbox.pack_start(info_box, False, False)
        vbox.pack_start(status_table, False, False)
        return vbox

    def make_error_tab(self, status_map, t):
        msg = status_map.lookup_error_msg(t)
        if isinstance(msg, str) or isinstance(msg, str):
            msg = msg.replace('<br/>', '\n')
        msg = '%s (%s)\n%s' % (t.label_en, t.label_zw, msg)
        label = ful.make_label(msg,
                               font=LABEL_EN_FONT,
                               alignment=(0.0, 0.0))
        label.set_line_wrap(True)
        frame = gtk.Frame()
        frame.add(label)
        return frame

    def key_release_callback(self, widget, event):
        factory.log('key_release_callback %s(%s)' %
                    (event.keyval, gdk.keyval_name(event.keyval)))
        if event.keyval == ord('k'):
            self.notebook.prev_page()
        elif event.keyval == ord('j'):
            self.notebook.next_page()
        return True

    def register_callback(self, window):
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gdk.KEY_RELEASE_MASK)

    def run_once(self, status_file_path=None, test_list=None):

        factory.log('%s run_once' % self.__class__)

        status_map = factory.StatusMap(test_list, status_file_path)
        tests = sum(([(t, None)] +
                     list(product(getattr(t, 'subtest_list', []), [t]))
                     for t in test_list), [])

        self.notebook = gtk.Notebook()
        self.notebook.modify_bg(gtk.STATE_NORMAL, ful.BLACK)

        tab = self.make_summary_tab(status_map, tests)
        tab.set_border_width(TAB_BORDER)
        self.notebook.append_page(tab, ful.make_label('Summary'))

        ts = (t for t, _ in tests
                if not isinstance(t, AutomatedSequence) and \
                   status_map.lookup_status(t) == ful.FAILED)
        for i, t in izip(count(1), ts):
            if not isinstance(t, AutomatedSequence) and \
               status_map.lookup_status(t) == ful.FAILED:
                tab = self.make_error_tab(status_map, t)
                tab.set_border_width(TAB_BORDER)
                self.notebook.append_page(tab, ful.make_label('#%02d' % i))

        control_label = ful.make_label('Press j/k to change tabs',
                                       font=LABEL_EN_FONT,
                                       alignment=(0.5, 0.5))

        vbox = gtk.VBox()
        vbox.set_spacing(20)
        vbox.pack_start(control_label, False, False)
        vbox.pack_start(self.notebook, False, False)

        test_widget = gtk.EventBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        test_widget.add(vbox)

        ful.run_test_widget(self.job, test_widget,
                            window_registration_callback=self.register_callback)

        factory.log('%s run_once finished' % self.__class__)
