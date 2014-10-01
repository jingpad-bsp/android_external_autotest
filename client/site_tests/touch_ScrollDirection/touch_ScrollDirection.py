# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import logging
import shutil

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import touch_playback_test_base


class touch_ScrollDirection(touch_playback_test_base.touch_playback_test_base):
    """Plays back scrolls and checks for correct page movement."""
    version = 1

    _VALID_BOARDS = ['squawks', 'nyan_big', 'parrot', 'link', 'peppy', 'daisy',
                     'peach_pit', 'x86-alex']

    def _check_scroll_direction(self, filename, down):
        """Playback and raise error if scrolling does not match down value.

        @param down: True if scrolling is supposed to be down; else False.

        @raises TestFail if actual scrolling did not match expected.

        """
        self._reload_page()
        self._wait_for_default_scroll_position()
        self._playback(filepath=filename)
        self._wait_for_scroll_position_to_settle()

        delta = self._get_scroll_position() - self._DEFAULT_SCROLL
        logging.info('Scroll delta was %d', delta)
        if (down and delta <= 0) or (not down and delta >= 0):
            raise error.TestFail('Page scroll was in wrong direction! '
                                 'Delta=%d, Australian=%s'
                                  % (delta, self._australian_state))

    def _verify_scrolling(self):
        """Check scrolling direction for down then up."""
        self._check_scroll_direction(filename=self._down_file,
                                     down=not self._australian_state)
        self._check_scroll_direction(filename=self._up_file,
                                     down=self._australian_state)

    def run_once(self):
        """Entry point of this test."""

        # Copy playback files to DUT, if available.  Deleted during cleanup.
        self._copied_files = []
        device = utils.get_board()
        if device not in self._VALID_BOARDS:
            logging.info('Aborting test; %s is not supported.', device)
            return
        gestures_dir = os.path.join(self.bindir, 'gestures')
        down = device + '_scroll_down'
        up = device + '_scroll_up'
        self._down_file = os.path.join('/tmp', down)
        self._up_file = os.path.join('/tmp', up)
        self._copied_files.append(self._down_file)
        self._copied_files.append(self._up_file)
        shutil.copyfile(os.path.join(gestures_dir, down), self._down_file)
        shutil.copyfile(os.path.join(gestures_dir, up), self._up_file)

        # Raise error if no touchpad detected.
        if not self._has_touchpad:
            raise error.TestFail('No touchpad found on this %d' % device)

        # Log in and start test.
        with chrome.Chrome() as cr:
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

    def cleanup(self):
        # Remove files, if present.
        for fh in self._copied_files:
            try:
                os.remove(fh)
            except OSError:
                pass


