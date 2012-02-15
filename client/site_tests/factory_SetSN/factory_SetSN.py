# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# Select a unique serial number to write to VPD.
# Partners should fill this in with the correct serial number
# printed on the box and physical device.

import datetime
import gtk
import pango
import sys
import utils

from gtk import gdk

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import ui as ful


class factory_SetSN(test.test):
    version = 1

    def write_vpd(self, serial_number):
        cmd = ('vpd -i RO_VPD '
               '-s "serial_number"="%s" '
               % serial_number)
        utils.system_output(cmd)

    def on_complete(self, serial_number):
        if self.writing:
            return True

        factory.log(' sn is %s' % serial_number)
        self.writing = True

        # Display one single label.
        self.test_widget.remove(self.sn_widget)
        self.label = ful.make_label(
                'Writing serial number: %s\n'
                'Please wait... (may take >10s)' % serial_number)
        self.test_widget.add(self.label)
        self.test_widget.show_all()
        while gtk.events_pending():
            gtk.main_iteration(False)
        self.write_vpd(serial_number)
        gtk.main_quit()

    def on_keypress(self, entry, key):
        if key.keyval == gtk.keysyms.Tab:
            entry.set_text('InvalidSN-%s' % datetime.datetime.now().
                           strftime('%Y%m%d-%H%M%S'))
            return True
        return False

    def run_once(self):

        factory.log('%s run_once' % self.__class__)

        self.writing = False
        self.test_widget = gtk.VBox()
        # TODO(hungte) add other hot key to load "current serial number"
        self.sn_widget = ful.make_input_window(
                prompt='Enter Serial Number (TAB to insert testing random SN):',
                on_keypress=self.on_keypress,
                on_complete=self.on_complete)
        self.test_widget.add(self.sn_widget)

        ful.run_test_widget(self.job, self.test_widget)

        factory.log('%s run_once finished' % repr(self.__class__))
