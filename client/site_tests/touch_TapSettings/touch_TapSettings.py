# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import itertools
import os
import logging
import shutil
import time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import touch_playback_test_base


class touch_TapSettings(touch_playback_test_base.touch_playback_test_base):
    """Toggles tap-to-click and tap dragging settings to ensure correctness."""
    version = 1

    _test_timeout = 3 # Number of seconds the test will wait for a click.
    _click_name = 'tap_click' # Suffix for files containing a tap-to-click.
    _drag_name = 'tap_drag' # Suffix for files containing a tap drag.

    def _check_for_click(self, expected):
        """Playback and check whether tap-to-click occurred.  Fail if needed.

        @param expected: True if clicking should happen, else False.
        @raises: TestFail if actual value does not match expected.

        """
        expected_count = 1 if expected else 0
        self._reload_page()
        self._playback(filepath=self._files[self._click_name])
        time.sleep(self._test_timeout)
        actual_count = int(self._tab.EvaluateJavaScript('clickCount'))
        if actual_count is not expected_count:
            raise error.TestFail('Expected clicks=%s, actual=%s.'
                                 % (expected_count, actual_count))


    def _check_for_drag(self, expected):
        """Playback and check whether tap dragging occurred.  Fail if needed.

        @param expected: True if dragging should happen, else False.
        @raises: TestFail if actual value does not match expected.

        """
        self._reload_page()
        self._playback(filepath=self._files[self._drag_name])
        time.sleep(self._test_timeout)
        actual = self._tab.EvaluateJavaScript('movementOccurred')
        if actual is not expected:
            raise error.TestFail('Tap dragging movement was %s; expected %s.'
                                 % (actual, expected))


    def run_once(self):
        """Entry point of this test."""

        # Copy playback files to DUT, if available.  Deleted during cleanup.
        self._files = dict()
        device = utils.get_board()
        gestures_dir = os.path.join(self.bindir, 'gestures')
        for elt in [self._click_name, self._drag_name]:
            filename = '%s_%s' % (device, elt)
            original_file = os.path.join(gestures_dir, filename)
            self._files[elt] = os.path.join('/tmp', filename)
            try:
                shutil.copyfile(original_file, self._files[elt])
            except IOError:
                raise error.TestNAError('Aborting test; %s is not supported.' %
                                        device)

        # Raise error if no touchpad detected.
        if not self._has_touchpad:
            raise error.TestFail('No touchpad found on this %d' % device)

        # Log in and start test.
        with chrome.Chrome() as cr:
            # Open test page.
            cr.browser.SetHTTPServerDirectories(self.bindir)
            self._tab = cr.browser.tabs[0]
            self._tab.Navigate(cr.browser.http_server.UrlOf(
                    os.path.join(self.bindir, 'test_page.html')))
            self._tab.WaitForDocumentReadyStateToBeComplete()

            # Check default setting values.
            logging.info('Checking for default setting values.')
            self._check_for_click(True)
            self._check_for_drag(False)

            # Toggle settings in all combinations and check.
            options = [True, False]
            option_pairs = itertools.product(options, options)
            for (click_value, drag_value) in option_pairs:
                self._set_tap_to_click(click_value)
                self._set_tap_dragging(drag_value)
                self._check_for_click(click_value)
                self._check_for_drag(click_value and drag_value)


    def cleanup(self):
        # Remove file, if present.
        for filetype in self._files:
            try:
                os.remove(self._files[filetype])
            except OSError:
                pass


