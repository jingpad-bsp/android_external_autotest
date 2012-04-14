# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import glob
import logging
import os
import re
import utils

from autotest_lib.client.bin import test
from autotest_lib.client.bin.input.input_device import *
from autotest_lib.client.bin.input.input_event_player import *
from autotest_lib.client.common_lib import error

XORG_LOG = '/var/log/Xorg.0.log'


class platform_TouchpadSynDrop(test.test):
    version = 1

    def _mygrep(self, fname, substring, starting=0):
        lines = []
        i = 0
        for line in open(fname, 'rt'):
            if i >= starting and substring in line:
                lines.append(line)
            i += 1
        return lines

    def _get_first_touchpad_device(self):
        for evdev in glob.glob('/dev/input/event*'):
            device = InputDevice(evdev)
            if device.is_touchpad():
                return device
        return None

    def _test_if_syn_dropped_processed(self):
        # Get the first touchpad device to test
        device = self._get_first_touchpad_device()
        if not device:
            raise error.TestError('Can not find a touchpad device')
        # Get current number of lines in Xorg.0.log
        cmd = ('/usr/bin/wc -l %s | /usr/bin/cut -d \' \' -f1' % XORG_LOG)
        bn = int(utils.system_output(cmd))

        # Bombard the evdev driver
        player = InputEventPlayer()
        player.playback(device, self.gestures_dir + '/bombard.dat')

        # Test if we see SYN_DROPPED and process it.
        if not self._mygrep(XORG_LOG, 'SYN_DROPPED', bn):
            raise error.TestFail('Did not see SYN_DROPPED event')
        if not self._mygrep(XORG_LOG, 'Event_Sync_State', bn):
            raise error.TestFail('Did not see Event_Sync_State action')

    def run_once(self):
        self.gestures_dir = os.path.join(self.bindir, 'gestures')
        self._test_if_syn_dropped_processed()
        self.job.set_state('client_passed', True)
