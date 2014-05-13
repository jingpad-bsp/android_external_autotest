# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib.cros import chrome, enrollment


class enterprise_RemoraRequisition(test.test):
    """Enroll as a Remora device."""
    version = 1

    def run_once(self):
        if enrollment.ClearTPM():
            return

        user_id, password = utils.get_signin_credentials(os.path.join(
                os.path.dirname(os.path.realpath(__file__)), 'credentials.txt'))
        if user_id and password:
            with chrome.Chrome(auto_login=False) as cr:
                enrollment.RemoraEnrollment(cr.browser, user_id, password)
                # TODO(achuith): Additional logic to ensure the hangouts app is
                # functioning correctly.

            enrollment.ClearTPM()
        else:
            logging.warn('No credentials found - exiting test.')
