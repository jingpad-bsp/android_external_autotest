# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# Select the keyboard type, and write to VPD.


import gtk
import pango
import sys
import utils

from gtk import gdk

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

# Mapping between menu choice and KB.
kb_map = {
  '1': ('United States', 'en-US', 'xkb:us::eng'),
  '2': ('United Kingdom', 'en-GB', 'xkb:gb:extd:eng'),
  'q': ('None', None, None)
}

# Message to display.
msg = ('Choose a keyboard:\n' +
      "".join([ '%s) %s - %s\n' % (i, kb_map[i][0], kb_map[i][1])
                                   for i in sorted(kb_map)]))

class factory_SelectKeyboard(test.test):
    version = 1

    def write_kb(self, kb):
        cmd = 'vpd -i RO_VPD -s "initial_locale"="%s"' % kb[1]
        utils.system_output(cmd)
        cmd = 'vpd -i RO_VPD -s "keyboard_layout"="%s"' % kb[2]
        utils.system_output(cmd)

    def key_release_callback(self, widget, event):
        char = event.keyval in range(32,127) and chr(event.keyval) or None
        factory.log('key_release %s(%s)' % (event.keyval, char))
        if char in kb_map:
          kb = kb_map[char]
          factory.log('Keyboard specified as %s, (pressed %s)' % (
              kb, char))

          if kb:
            self.write_kb(kb)

          gtk.main_quit()
        return True

    def register_callbacks(self, window):
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gdk.KEY_RELEASE_MASK)

    def run_once(self):

        factory.log('%s run_once' % self.__class__)
        label = ful.make_label(msg)

        test_widget = gtk.EventBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        test_widget.add(label)

        ful.run_test_widget(self.job, test_widget,
            window_registration_callback=self.register_callbacks)

        factory.log('%s run_once finished' % repr(self.__class__))
