# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import touch_playback_test_base


class touch_TouchscreenScroll(
        touch_playback_test_base.touch_playback_test_base):
    """Plays back scrolls and checks for correct page movement."""
    version = 1

    _DIRECTIONS = ['down', 'up', 'right', 'left']
    _REVERSES = {'down': 'up', 'up': 'down', 'right': 'left', 'left': 'right'}


    def _check_scroll_direction(self, filepath, expected):
        """Playback and raise error if scrolling does not match down value.

        @param filepath: Gesture file's complete path for playback.
        @param expected: String, expected direction in which test page scroll
                         should move for the gesture file being played.

        @raises TestFail if actual scrolling did not match expected.

        """
        is_vertical = expected == 'up' or expected == 'down'
        is_down_or_right = expected == 'down' or expected == 'right'

        self._set_default_scroll_position(is_vertical)
        self._wait_for_default_scroll_position(is_vertical)
        self._playback(filepath, touch_type='touchscreen')
        self._wait_for_scroll_position_to_settle(is_vertical)
        delta = self._get_scroll_position(is_vertical) - self._DEFAULT_SCROLL
        logging.info('Scroll delta was %d', delta)

        # Check if movement occured in correct direction.
        if ((is_down_or_right and delta <= 0) or
            (not is_down_or_right and delta >= 0)):
            raise error.TestFail('Page scroll was in wrong direction! '
                                 'Delta=%d' % delta)


    def _is_testable(self):
        """Return True if test can run on this device, else False.

        @raises: TestError if host has no touchscreen when it should.

        """
        # Check if playback files are available on DUT to run test.
        self._device = utils.get_board()
        gest_dir = os.path.join(self.bindir, 'gestures')
        self._filepaths = {}

        for direction in self._DIRECTIONS:
            gest_file = '%s_touchscreen_scroll_%s' % (self._device, direction)
            self._filepaths[direction] = os.path.join(gest_dir, gest_file)
            if not os.path.exists(self._filepaths[direction]):
                logging.info('Missing gesture files, Aborting test')
                return False

        # Raise error if no touchscreen detected.
        if not self._has_touchscreen:
            raise error.TestError('No touchscreen found!')

        return True


    def run_once(self):
        """Entry point of this test."""
        if not self._is_testable():
            return

        # Log in and start test.
        with chrome.Chrome(autotest_ext=True) as cr:
            self._open_test_page(cr)
            for direction in self._DIRECTIONS:
                self._check_scroll_direction(self._filepaths[direction],
                                             self._REVERSES[direction])
