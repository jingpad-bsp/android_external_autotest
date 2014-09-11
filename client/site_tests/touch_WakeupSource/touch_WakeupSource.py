# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import touch_playback_test_base


class touch_WakeupSource(touch_playback_test_base.touch_playback_test_base):
    """Check that touchpad/touchscreen are set/not set as wake sources."""
    version = 1

    # Devices whose touchpads should not be a wake source.
    _NO_TOUCHPAD_WAKE = ['clapper', 'glimmer']

    # Devices with Synaptics touchpads that do not report wake source.
    _INVALID_BOARDS = ['x86-alex', 'x86-alex_he', 'x86-zgb', 'x86-zgb_he',
                       'x86-mario']

    _NODE_CMD = 'cat /sys/class/input/input%s/device/power/wakeup'

    def _is_wake_source(self, input_type):
        """Return True if the given device is a wake source, else False.

        @param input_type: e.g. 'touchpad' or 'mouse'. See parent class for
                all options.

        @raises: TestError if it cannot interpret file contents.

        """
        node = self._nodes[input_type]
        node_num = re.search('event([0-9]+)', node).group(1)
        result = utils.run(self._NODE_CMD % node_num).stdout.strip()
        if result == 'enabled':
            return True
        elif result == 'disabled':
            return False
        error.TestError('wakeup file for %s on input%s said "%s".' %
                        (input_type, node_num, result))

    def run_once(self):
        """Entry point of this test."""

        # Check that touchpad is a wake source for all but the excepted boards.
        if self._has_touchpad:
            device = utils.get_board()
            if device not in self._INVALID_BOARDS:
                if device in self._NO_TOUCHPAD_WAKE:
                    if self._is_wake_source('touchpad'):
                        raise error.TestFail('Touchpad is a wake source!')
                else:
                    if not self._is_wake_source('touchpad'):
                        raise error.TestFail('Touchpad is not a wake source!')

        # Check that touchscreen is not a wake source (if present).
        if self._has_touchscreen:
            if self._is_wake_source('touchscreen'):
                raise error.TestFail('Touchpad is a wake source!')
