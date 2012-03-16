# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Factory task to select an unique serial number for VPD.

Partners should fill this in with the correct serial number
printed on the box and physical device.
"""

import gtk

from autotest_lib.client.cros.factory import task
from autotest_lib.client.cros.factory import ui


# The "ESC" is available primarily for RMA and testing process, when operator
# does not want to change existing serial number.
# TODO(hungte) When the factory framework supports caching firmware in the
# beginning, we should change ESC to "load current serial number" instead of
# "skip", so that a device without any serial number won't pass this test.
_MESSAGE_PROMPT = ('Enter Serial Number:\n'
                   ' (ESC to leave current serial number unmodified)')


class SerialNumberTask(task.FactoryTask):

    def __init__(self, vpd):
        self.vpd = vpd

    def on_complete(self, serial_number):
        self.vpd['ro']['serial_number'] = serial_number.strip()
        self.stop()

    def on_entry_keypress(self, entry, key):
        if key.keyval == gtk.keysyms.Escape:
            self.stop()
            return True
        return False

    def start(self):
        self.add_widget(ui.make_input_window(prompt=_MESSAGE_PROMPT,
                                             on_keypress=self.on_entry_keypress,
                                             on_complete=self.on_complete))
