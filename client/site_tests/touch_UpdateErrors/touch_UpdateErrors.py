# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import touch_playback_test_base


class touch_UpdateErrors(touch_playback_test_base.touch_playback_test_base):
    """Check that there are no touch update errors."""
    version = 1

    def _check_updates(self):
        """Fail the test if device has any update errors for touch.

        @raises: TestFail if no update is found or if there is an error.

        """
        log_cmd = 'grep -i touch /var/log/messages'

        # Check for no errors in touch logs.
        for term in ['error', 'fail']:
            error_cmd = '%s | grep -i %s' % (log_cmd, term)
            error_logs = utils.run(error_cmd, ignore_status=True).stdout
            if len(error_logs) > 0:
                raise error.TestFail('Error: %s.' % error_logs.split('\n')[0])

    def run_once(self):
        """Entry point of this test."""

        # Skip run on devices which do not have touch inputs.
        if not self._has_touchpad and not self._has_touchscreen:
            logging.info('This device does not have a touch input source.')
            return

        self._check_updates()
