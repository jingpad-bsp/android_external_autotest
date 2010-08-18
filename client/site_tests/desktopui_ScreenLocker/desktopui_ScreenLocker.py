# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import gobject
import os
import time

from autotest_lib.client.bin import site_ui_test, site_utils
from autotest_lib.client.common_lib import error
from dbus.mainloop.glib import DBusGMainLoop

class desktopui_ScreenLocker(site_ui_test.UITest):
    version = 1
    _POWER_MANAGER_INTERFACE = 'org.chromium.PowerManager'

    def locked(self):
        self._locked = True

    def unlocked(self):
        self._locked = False

    def process_event(self):
        """Process dbus events"""
        context = gobject.MainLoop().get_context()
        while context.iteration(False):
            pass

    def is_screen_locked(self):
        self.process_event()
        return self._locked

    def is_screen_unlocked(self):
        self.process_event()
        return self._locked == False

    def run_once(self):
        self._locked = False
        self.listen_to_signal(lambda: self.locked(),
                              'ScreenIsLocked',
                              self._POWER_MANAGER_INTERFACE)
        self.listen_to_signal(lambda: self.unlocked(),
                              'ScreenIsUnlocked',
                              self._POWER_MANAGER_INTERFACE)
        # wait 2 seconds to make sure chrome registers
        # the accelerator.
        time.sleep(5);

        ax = self.get_autox()
        ax.send_hotkey('Ctrl-Alt-l')

        site_utils.poll_for_condition(
            condition=lambda: self.is_screen_locked(),
            desc='screenlocker lock')

        # send an incorrect password
        ax.send_text('_boguspassword_')
        ax.send_hotkey('Return')

        # verify that the screen unlock attempt failed
        try:
          site_utils.poll_for_condition(
              condition=lambda: self.is_screen_unlocked(),
              desc='screen unlock',
              timeout=5)
        except error.TestError:
            pass
        else:
            raise error.TestFail('screen locker unlocked with bogus password.')

        # send the correct password
        ax.send_text(self.password)
        ax.send_hotkey('Return')

        # wait for screen to unlock
        site_utils.poll_for_condition(
            condition=lambda: self.is_screen_unlocked(),
            desc='screenlocker unlock')
