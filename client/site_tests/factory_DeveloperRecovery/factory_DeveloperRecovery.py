# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# Intended for use during manufacturing to validate Developer mode
# switch and Recovery button function properly.  This program will
# display an image of the d-housing with Developer switch and Recovery
# button.  Operator will then be instructed via text and visually to
# switch and restore the Developer switch and press/release the
# Recovery button.  Success at each step resets a 20 second countdown timer.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import factory_test

import gtk
import cairo
import os

import DevRecTest

class factory_DeveloperRecovery(test.test):
    version = 1
    preserve_srcdir = True

    def key_release_callback(self, widget, event):
        char = event.keyval in range(32,127) and chr(event.keyval) or None
        factory_test.XXX_log('key_release_callback %s(%s)' %
                             (event.keyval, char))
        if event.keyval == self.quit_key:
            factory_test.XXX_log('%s exiting...' % self.tagged_testname)
            gtk.main_quit()
        factory_test.test_switch_on_trigger(event)
        return True

    def register_callbacks(self, window):
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gtk.gdk.KEY_RELEASE_MASK)

    def run_once(self, test_widget_size=None, trigger_set=None, layout='devrec',
        result_file_path=None, quit_key=ord('Q'),
        msg='factory_DeveloperRecovery'):

        factory_test.XXX_log(self.tagged_testname)

        self.quit_key = quit_key

        factory_test.init(trigger_set=trigger_set,
                          result_file_path=result_file_path)

        os.chdir(self.srcdir)
        dr_image = cairo.ImageSurface.create_from_png('%s.png' % layout)

        test_widget = DevRecTest.make_test_widget(self.autodir, dr_image)

        factory_test.run_test_widget(
            test_widget=test_widget,
            test_widget_size=test_widget_size,
            window_registration_callback=self.register_callbacks)

        factory_test.XXX_log('exiting %s' % self.tagged_testname)
