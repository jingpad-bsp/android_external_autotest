# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import touch_playback_test_base


class touch_UpdateErrors(touch_playback_test_base.touch_playback_test_base):
    """Check that touch update is tried and that there are no update errors."""
    version = 1

    # Older devices with Synaptics touchpads do not report firmware updates.
    _INVALID_BOARDS = ['x86-alex', 'x86-alex_he', 'x86-zgb', 'x86-zgb_he',
                       'x86-mario', 'stout']

    # Special exception for crosbug.com/p/31012, to be removed once
    # crbug.com/516886 is resolved.
    def _is_actual_error(self, err):
        """Returns True/False depending on whether this error is valid.

        @param err: the error message we are about to raise

        """
        exceptions = {'expresso': 'Tue Jul 15 22:26:57 PDT 2014',
                      'enguarde': 'Wed Jun 18 12:24:44 PDT 2014'}
        valid_error = 'No valid firmware for ELAN0000:00 found'
        if self.device in exceptions and err.find(valid_error) >= 0:
            matches = utils.run(
                    'grep "%s" /var/log/messages' % exceptions[self.device],
                    ignore_status=True).stdout
            if matches:
                logging.info('Ignoring failure from crosbug.com/p/31012!')
                return False
        return True

    def _check_updates(self):
        """Fail the test if device has problems with touch firmware update.

        @raises: TestFail if no update attempt occurs or if there is an error.

        """
        log_cmd = 'grep -i touch /var/log/messages'

        pass_terms = ['chromeos-touch-firmware-update']
        fail_terms = ['error:']

        # Check for key terms in touch logs.
        for term in pass_terms + fail_terms:
            search_cmd = '%s | grep -i %s' % (log_cmd, term)
            log_entries = utils.run(search_cmd, ignore_status=True).stdout
            if term in fail_terms and len(log_entries) > 0:
                error_msg = log_entries.split('\n')[0]
                error_msg = error_msg[error_msg.find(term)+len(term):].strip()
                if self._is_actual_error(error_msg):
                    raise error.TestFail(error_msg)
            if term in pass_terms and len(log_entries) == 0:
                raise error.TestFail('Touch firmware did not attempt update.')

    def run_once(self):
        """Entry point of this test."""

        # Skip run on devices which do not have touch inputs.
        if not self._has_touchpad and not self._has_touchscreen:
            logging.info('This device does not have a touch input source.')
            return

        # Skip run on invalid touch inputs.
        self.device = utils.get_board()
        if self.device.find('freon') >= 0:
            self.device = self.device[:-len('_freon')]
        if self.device in self._INVALID_BOARDS:
            logging.info('This touchpad is not supported for this test.')
            return

        self._check_updates()
