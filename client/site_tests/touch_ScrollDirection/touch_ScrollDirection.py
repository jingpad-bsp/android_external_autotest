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

    _DEFAULT_SCROLL = 100
    _VALID_BOARDS = ['squawks', 'nyan_big', 'parrot', 'link', 'peppy', 'daisy',
                     'peach_pit', 'x86-alex']

    def _get_page_position(self):
        """Return current scroll position of page."""
        return self._tab.EvaluateJavaScript('document.body.scrollTop')

    def _reset_page_position(self):
        """Reset page position to default."""
        self._tab.ExecuteJavaScript('window.scrollTo(0, %x)'
                                    % self._DEFAULT_SCROLL)

    def _check_scroll_direction(self, down):
        """Raise error if actual scrolling does not match down value.

        @param down: True if scrolling is supposed to be down; else False.

        @raises TestError if actual scrolling did not match down param.

        """
        current = self._get_page_position()
        logging.info('Scroll delta was %d', current - self._DEFAULT_SCROLL)
        if down:
            if current <= self._DEFAULT_SCROLL:
                raise error.TestError('Page did not scroll down! '
                                      'Australian=%s' % self._australian_state)
        else:
            if current >= self._DEFAULT_SCROLL:
                raise error.TestError('Page did not scroll up! '
                                      'Australian=%s' % self._australian_state)

    def _verify_scrolling(self):
        """Scroll down and check scroll direction, then repeat with up."""
        self._reset_page_position()
        self._playback(filepath=self._down_file)
        self._check_scroll_direction(down=not self._australian_state)

        self._reset_page_position()
        self._playback(filepath=self._up_file)
        self._check_scroll_direction(down=self._australian_state)

    def run_once(self):
        """Entry point of this test."""

        # Copy playback files to DUT, if available.  Deleted during cleanup.
        device = utils.get_board()
        if device not in self._VALID_BOARDS:
            logging.info('Aborting test; %s is not supported.', device)
            return
        self._copied_files = []
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
            logging.info('No touchpad found!')
            raise error.TestError('No touchpad found on this %d' % device)

        # Log in and start test.
        with chrome.Chrome() as cr:
            # Open test page.
            cr.browser.SetHTTPServerDirectories(self.bindir)
            self._tab = cr.browser.tabs[0]
            self._tab.Navigate(cr.browser.http_server.UrlOf(
                    os.path.join(self.bindir, 'long_page.html')))
            self._tab.WaitForDocumentReadyStateToBeComplete()

            # Check default scroll - australian for touchscreens.
            self._australian_state = self._has_touchscreen
            logging.info('Expecting Australian=%s', self._australian_state)
            self._verify_scrolling()

            # Toggle australian scrolling and check again.
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


