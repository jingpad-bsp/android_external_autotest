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
import sys


class factory_Dummy(test.test):
    version = 1

    def key_release_callback(self, widget, event):
        char = event.keyval in range(32,127) and chr(event.keyval) or None
        factory_test.XXX_log('key_release_callback %s(%s)' %
                             (event.keyval, char))
        if event.keyval == self.quit_key:
            factory_test.XXX_log('factory_Dummy exiting...')
            gtk.main_quit()
        factory_test.test_switch_on_trigger(event)
        return True

    def register_callbacks(self, window):
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gtk.gdk.KEY_RELEASE_MASK)

    def run_once(self, test_widget_size=None, trigger_set=None,
                 result_file_path=None, quit_key=ord('Q'), msg='factory_Dummy'):

        factory_test.XXX_log('factory_Dummy')

        self.quit_key = quit_key

        factory_test.init(trigger_set=trigger_set,
                          result_file_path=result_file_path)

        label = gtk.Label(msg)
        label.modify_font(pango.FontDescription('courier new condensed 20'))
        label.set_alignment(0.5, 0.5)
        label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse('light green'))

        test_widget = gtk.EventBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
        test_widget.add(label)

        factory_test.run_test_widget(
            test_widget=test_widget,
            test_widget_size=test_widget_size,
            window_registration_callback=self.register_callbacks)

        factory_test.XXX_log('exiting factory_Dummy')
