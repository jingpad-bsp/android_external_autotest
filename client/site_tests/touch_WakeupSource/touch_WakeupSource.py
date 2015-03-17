# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import touch_playback_test_base


class touch_WakeupSource(touch_playback_test_base.touch_playback_test_base):
    """Check that touchpad/touchscreen are set/not set as wake sources."""
    version = 1

    # Devices whose touchpads should not be a wake source.
    _NO_TOUCHPAD_WAKE = ['clapper', 'glimmer', 'veyron_minnie']

    # Devices with Synaptics touchpads that do not report wake source.
    _INVALID_BOARDS = ['x86-alex', 'x86-alex_he', 'x86-zgb', 'x86-zgb_he',
                       'x86-mario', 'stout']

    _NODE_FILE = '/sys/class/input/input%s/device/power/wakeup'

    def _is_wake_source(self, input_type):
        """Return True if the given device is a wake source, else False.

        Also, return false if the file does not exist.

        @param input_type: e.g. 'touchpad' or 'mouse'. See parent class for
                all options.

        @raises: TestError if it cannot interpret file contents.

        """
        node = self._nodes[input_type]
        node_num = re.search('event([0-9]+)', node).group(1)

        filename = self._NODE_FILE % node_num
        if not os.path.isfile(filename):
            logging.info('%s not found for %s', filename, input_type)
            return False

        result = utils.run('cat %s' % filename).stdout.strip()
        if result == 'enabled':
            logging.info('Found that %s is a wake source.', input_type)
            return True
        elif result == 'disabled':
            logging.info('Found that %s is not a wake source.', input_type)
            return False
        error.TestError('wakeup file for %s on input%s said "%s".' %
                        (input_type, node_num, result))

    def run_once(self):
        """Entry point of this test."""

        # Check that touchpad is a wake source for all but the excepted boards.
        if self._has_touchpad:
            device = utils.get_board()
            if device.find('freon') >= 0:
                device = device[:-len('_freon')]
            if device not in self._INVALID_BOARDS:
                if device in self._NO_TOUCHPAD_WAKE:
                    if self._is_wake_source('touchpad'):
                        raise error.TestFail('Touchpad is a wake source!')
                else:
                    if not self._is_wake_source('touchpad'):
                        raise error.TestFail('Touchpad is not a wake source!')

        # Check that touchscreen is not a wake source (if present).
        # Devices without a touchpad should have touchscreen as wake source.
        if self._has_touchscreen:
            touchscreen_wake = self._is_wake_source('touchscreen')
            if self._has_touchpad and touchscreen_wake:
                raise error.TestFail('Touchscreen is a wake source!')
            if not self._has_touchpad and not touchscreen_wake:
                raise error.TestFail('Touchscreen is not a wake source!')

