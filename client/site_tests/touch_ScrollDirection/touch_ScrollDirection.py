# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import logging

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import touch_playback_test_base


class touch_ScrollDirection(touch_playback_test_base.touch_playback_test_base):
    """Plays back scrolls and checks for correct page movement."""
    version = 1

    _MOUSE_DESCRIPTION = 'apple_mouse.prop'
    _DIRECTIONS = ['down', 'up', 'right', 'left']
    _REVERSES = {'down': 'up', 'up': 'down', 'right': 'left', 'left': 'right'}


    def _wait_for_page_ready(self):
        utils.poll_for_condition(
                lambda: self._tab.EvaluateJavaScript('pageReady'),
                exception=error.TestError('Test page is not ready!'))


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
        self._playback(filepath)
        self._wait_for_scroll_position_to_settle(is_vertical)
        delta = self._get_scroll_position(is_vertical) - self._DEFAULT_SCROLL
        logging.info('Scroll delta was %d', delta)

        # Below logic checks if the scroll has occurd in right direction taking
        # into account Australian_scroll setting and the direction of
        # scroll's movement and fails the test if scroll occured in wrong direction.
        if (is_down_or_right and delta <= 0) or (not is_down_or_right and delta >= 0):
            raise error.TestFail('Page scroll was in wrong direction! '
                                 'Delta=%d, Australian=%s, Touchscreen=%s'
                                  % (delta, self._australian_state,
                                     self._has_touchscreen))


    def _center_cursor(self):
        """Playback and check whether cursor moved as recorded. Fail if needed.

        @raises: TestError if cursor movement is not recorded in test_page.html.

        """
        self._reload_page()
        self._wait_for_page_ready()
        self._blocking_playback(self._center_cursor_file,
                                touch_type='mouse')
        if not self._tab.EvaluateJavaScript('cursorOnPage'):
            raise error.TestError('Test page did not see cursor.')


    def _verify_scrolling(self):
        """Check scrolling direction for down then up."""

        if not self._australian_state:
            for direction in self._DIRECTIONS:
                self._check_scroll_direction(self._filepaths[direction],
                                             direction)
        else:
            for direction in self._DIRECTIONS:
                self._check_scroll_direction(self._filepaths[direction],
                                             self._REVERSES[direction])


    def _is_testable(self):
        """Return True if test can run on this device, else False.

        @raises: TestError if host has no touchpad when it should.

        """
        # Check if playback files are available on DUT to run test.
        self._device = utils.get_board()
        gest_dir = os.path.join(self.bindir, 'gestures')
        self._center_cursor_file = os.path.join(gest_dir, 'center_cursor')
        self._filepaths = {}

        for direction in self._DIRECTIONS:
            gest_file =  '%s_scroll_%s' % (self._device, direction)
            self._filepaths[direction] = os.path.join(gest_dir, gest_file)
            if not os.path.exists(self._filepaths[direction]):
                logging.info('Missing gesture files, Aborting test')
                return False

        # Raise error if no touchpad detected.
        if not self._has_touchpad:
            raise error.TestError('No touchpad found on this %d' % self._device)

        return True


    def _page_setup(self, cr):
        """Prepare for test by opening test page and centering cursor.

        Navigate to test page, emulate a USB mouse, and center the cursor.

        @raises: TestError if mouse emulation fails.

        """
        # Open test page.
        cr.browser.SetHTTPServerDirectories(self.bindir)
        self._tab = cr.browser.tabs[0]
        self._tab.Navigate(cr.browser.http_server.UrlOf(
                os.path.join(self.bindir, 'long_page.html')))
        self._tab.WaitForDocumentReadyStateToBeComplete()
        self._wait_for_page_ready()

        # Emulate a USB test mouse and center cursor.
        mouse_file = os.path.join(self.bindir, self._MOUSE_DESCRIPTION)
        self._emulate_mouse(property_file=mouse_file)
        if not self._has_mouse:
            raise error.TestError('Emulated mouse not found on device.')
        self._center_cursor()


    def run_once(self):
        """Entry point of this test."""
        if not self._is_testable():
            return

        # Log in and start test.
        with chrome.Chrome(autotest_ext=True) as cr:
            # Pass in the autotest extension.
            self._set_autotest_ext(cr.autotest_ext)
            self._page_setup(cr)

            # Check default scroll - Australian for touchscreens.
            self._australian_state = self._has_touchscreen
            logging.info('Expecting Australian=%s', self._australian_state)
            self._verify_scrolling()

            # Toggle Australian scrolling and check again.
            self._australian_state = not self._australian_state
            self._set_australian_scrolling(value=self._australian_state)
            self._verify_scrolling()
