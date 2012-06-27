# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

'''Displays a message to the operator and waits for the space bar to be
pressed.  Optionally lights all LEDs.

Args:
    message: The message to display.
    light_leds: True to cause all LEDs to be lit.  (The LEDs will be
        reset before the test exits.)
'''

import gtk

from autotest_lib.client.bin import test
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import leds
from cros.factory.test import ui


class factory_Prompt(test.test):
    version = 1

    def run_once(self,
                 message,
                 light_leds=False):
        if light_leds:
            leds.SetLeds(leds.LED_SCR|leds.LED_NUM|leds.LED_CAP)

        try:
            vbox = gtk.VBox()
            vbox.add(ui.make_label(message, font=ui.LABEL_LARGE_FONT))

            def register_window(window):
                def check_space(window, event):
                    if event.keyval == gtk.keysyms.space:
                        gtk.main_quit()

                callback = window.connect('key-press-event', check_space)

            ui.run_test_widget(
                self.job, vbox,
                window_registration_callback=register_window)
        finally:
            if light_leds:
                leds.SetLeds(0)
