# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import glob
import os

import utils

from autotest_lib.client.bin import test
from autotest_lib.client.bin.input.input_device import *
from autotest_lib.client.bin.input.input_event_player import *
from autotest_lib.client.common_lib import error

XORG_LOG = '/var/log/Xorg.0.log'


class platform_TouchscreenSynDrop(test.test):
    """
    The class is used to bombard the touchscreen device by filling up its
    the event queue for generating the SYN_DROPPED event. Therefore, we could
    test if touchscreen still function correctly after SYN_DROPPED event is
    handled.
    """
    version = 1

    def _mygrep(self, fname, substring, starting=0):
        lines = []
        i = 0
        for line in open(fname, 'rt'):
            if i >= starting and substring in line:
                lines.append(line)
            i += 1
        return lines

    def _get_first_touchscreen_device(self):
        for evdev in glob.glob('/dev/input/event*'):
            device = InputDevice(evdev)
            if device.is_touchscreen():
                return device
        return None

    def _test_if_syn_dropped_processed(self):
        # Get the first touchscreen device to test
        device = self._get_first_touchscreen_device()
        if not device:
            raise error.TestError('Can not find a touchscreen device')
        # Get current number of lines in Xorg.0.log
        cmd = ('/usr/bin/wc -l %s | /usr/bin/cut -d \' \' -f1' % XORG_LOG)
        bn = int(utils.system_output(cmd))

        # Bombard the evdev driver
        bombard_data = os.path.join(self.gestures_dir, 'bombard.dat')
        player = InputEventPlayer()
        for i in range(0, 100):
            player.playback(device, bombard_data)

        # Test if we see SYN_DROPPED and process it.
        if not self._mygrep(XORG_LOG, 'SYN_DROPPED', bn):
            raise error.TestFail('Did not see SYN_DROPPED event')
        if not self._mygrep(XORG_LOG, 'Sync_State', bn):
            raise error.TestFail('Did not see Sync_State action')

    def run_once(self):
        self.gestures_dir = os.path.join(self.bindir, 'gestures')
        self._test_if_syn_dropped_processed()
        self.job.set_state('client_passed', True)
