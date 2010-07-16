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

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


class factory_Review(test.test):
    version = 1

    def key_release_callback(self, widget, event):
        char = event.keyval in range(32,127) and chr(event.keyval) or None
        factory.log('key_release %s(%s)' % (event.keyval, char))
        self._ft_state.exit_on_trigger(event)
        return True

    def register_callbacks(self, window):
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gdk.KEY_RELEASE_MASK)

    def run_once(self,
                 test_widget_size=None,
                 trigger_set=None,
                 status_file_path=None,
                 test_list=None):

        factory.log('%s run_once' % self.__class__)

        self._ft_state = ful.State(trigger_set)

        status_map = ful.StatusMap(status_file_path, test_list)
        untested = status_map.filter(ful.UNTESTED)
        passed = status_map.filter(ful.PASSED)
        failed = status_map.filter(ful.FAILED)

        label = ful.make_label('UNTESTED=%d\n' % len(untested) +
                               'PASSED=%d\n' % len(passed) +
                               'FAILED=%d\n' % len(failed))

        test_widget = gtk.EventBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        test_widget.add(label)

        self._ft_state.run_test_widget(
            test_widget=test_widget,
            test_widget_size=test_widget_size,
            window_registration_callback=self.register_callbacks)

        factory.log('%s run_once finished' % self.__class__)
