# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This is an example factory test that does not really do anything --
# it displays a message in the center of the testing area, as
# communicated by arguments to run_once().  This test makes use of the
# ui_lib library to display its UI, and to monitor keyboard
# events for test-switching triggers.  This test can be terminated by
# typing SHIFT-Q.


import gtk
import logging
import pango
import sys

from gtk import gdk
from itertools import count, izip, product

from autotest_lib.client.bin import test
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import ui as ful

# Expose the class into the namespace rather than "from factory import <class>"
AutomatedSequence = factory.AutomatedSequence

LABEL_EN_FONT = pango.FontDescription('courier new extra-condensed 16')
TAB_BORDER = 20

def trim(text, length):
    if len(text) > length:
        text = text[:length-3] + '...'
    return text

class factory_Review(test.test):
    version = 1

    def make_error_tab(self, test, state):
        msg = str(state.error_msg).replace('<br/>', '\n')
        msg = '%s (%s)\n%s' % (test.label_en, test.label_zh, msg)
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

    def run_once(self, status_file_path=None, test_list_path=None):
        test_list = factory.read_test_list(test_list_path)
        state_map = test_list.get_state_map()

        self.notebook = gtk.Notebook()
        self.notebook.modify_bg(gtk.STATE_NORMAL, ful.BLACK)

        tab, _ = ful.make_summary_box([test_list], state_map)
        tab.set_border_width(TAB_BORDER)
        self.notebook.append_page(tab, ful.make_label('Summary'))

        for i, t in izip(
            count(1),
            [t for t in test_list.walk()
             if state_map[t].status == factory.TestState.FAILED
             and t.is_leaf()]):
            tab = self.make_error_tab(t, state_map[t])
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

        factory.log('Done with review')
