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
import pango
import sys

from gtk import gdk

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import factory
from cros.factory.test import ui as ful


class factory_Dummy(test.test):
    version = 1

    def key_release_callback(self, widget, event):
        char = event.keyval in range(32,127) and chr(event.keyval) or None
        factory.log('key_release %s(%s)' % (event.keyval, char))
        if event.keyval == self._quit_key:
            gtk.main_quit()
        return True

    def register_callbacks(self, window):
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gdk.KEY_RELEASE_MASK)

    def run_once(self,
                 quit_key=ord('Q'),
                 msg='factory_Dummy'):

        factory.log('%s run_once' % self.__class__)

        self._quit_key = quit_key

        label = ful.make_label(msg)

        test_widget = gtk.EventBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        test_widget.add(label)

        ful.run_test_widget(self.job, test_widget,
            window_registration_callback=self.register_callbacks)

        factory.log('%s run_once finished' % repr(self.__class__))
