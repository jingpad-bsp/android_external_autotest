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

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


class factory_SetSN(test.test):
    version = 1

    def write_vpd(self, serial_number):
        cmd = ('vpd -i RO_VPD '
               '-s "serial_number"="%s" '
               % serial_number)
        utils.system_output(cmd)

    def enter_callback(self, widget, entry):
        if self.writing:
            return True

        serial_number = entry.get_text()
        if not serial_number:
            serial_number=('InvalidSN-%s' %
                datetime.datetime.now().strftime('%Y-%m-%d-%H:%M:%S'))
        factory.log(' sn is %s' % serial_number)
        self.writing = True

        self.write_vpd(serial_number)
        gtk.main_quit()

    def register_callbacks(self, window):
        pass

    def run_once(self):

        factory.log('%s run_once' % self.__class__)

        self.writing = False
        self.test_widget = gtk.VBox()
        self.label = ful.make_label(
            'Enter Serial Number (Blank for testing only):')
        entry = gtk.Entry()
        entry.connect("activate", self.enter_callback, entry)
        self.test_widget.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        self.test_widget.add(self.label)
        self.test_widget.pack_start(entry)

        ful.run_test_widget(self.job, self.test_widget)

        factory.log('%s run_once finished' % repr(self.__class__))
