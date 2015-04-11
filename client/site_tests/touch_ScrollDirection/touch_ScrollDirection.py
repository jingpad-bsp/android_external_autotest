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

    def _check_scroll_direction(self, filepath, down):
        """Playback and raise error if scrolling does not match down value.

        @param down: True if scrolling is supposed to be down; else False.

        @raises TestFail if actual scrolling did not match expected.

        """
        self._set_default_scroll_position()
        self._wait_for_default_scroll_position()
        self._playback(filepath)
        self._wait_for_scroll_position_to_settle()

        delta = self._get_scroll_position() - self._DEFAULT_SCROLL
        logging.info('Scroll delta was %d', delta)
        if (down and delta <= 0) or (not down and delta >= 0):
            raise error.TestFail('Page scroll was in wrong direction! '
                                 'Delta=%d, Australian=%s'
                                  % (delta, self._australian_state))

    def _verify_scrolling(self):
        """Check scrolling direction for down then up."""

        self._check_scroll_direction(filepath=self._down_filepath,
                                     down=not self._australian_state)
        self._check_scroll_direction(filepath=self._up_filepath,
                                     down= self._australian_state)

    def run_once(self):
        """Entry point of this test."""
        # Check if corresponding playback files are available on DUT.
        device = utils.get_board()
        gest_dir = os.path.join(self.bindir, 'gestures')
        self._down_file = '%s_scroll_down' % device
        self._up_file = '%s_scroll_up' % device
        self._down_filepath = os.path.join(gest_dir, self._down_file)
        self._up_filepath = os.path.join(gest_dir, self._up_file)
        if not (os.path.exists(self._down_filepath) and
                os.path.exists (self._up_filepath)):
            logging.info('Missing gesture files, Aborting test')
            return

        # Raise error if no touchpad detected.
        if not self._has_touchpad:
            raise error.TestFail('No touchpad found on this %s' % device)

        # Log in and start test.
        with chrome.Chrome(autotest_ext=True) as cr:
            # Pass in the autotest extension.
            self._set_autotest_ext(cr.autotest_ext)

            # Open test page.
            cr.browser.SetHTTPServerDirectories(self.bindir)
            self._tab = cr.browser.tabs[0]
            self._tab.Navigate(cr.browser.http_server.UrlOf(
                               os.path.join(self.bindir, 'long_page.html')))
            self._tab.WaitForDocumentReadyStateToBeComplete()

            # Check default scroll - Australian for touchscreens.
            self._australian_state = self._has_touchscreen
            logging.info('Expecting Australian=%s', self._australian_state)
            self._verify_scrolling()

            # Toggle Australian scrolling and check again.
            self._australian_state = not self._australian_state
            self._set_australian_scrolling(value=self._australian_state)
            self._verify_scrolling()
