# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros import servo_test


class platform_ServoPyAuto(servo_test.ServoTest):
    """
    A simple test demonstrating the synchronous use of Servo and PyAuto.

    The client is logged in using PyAuto, the device is put to sleep by closing
    the lid with Servo, then the device is woken up by opening the lid and the
    test asserts that the user is still logged in.
    """
    version = 1


    def run_once(self, host=None):
        self.pyauto.LoginToDefaultAccount()

        # Close and open lid.
        boot_id = host.get_boot_id()
        host.servo.lid_close()
        host.test_wait_for_sleep()
        host.servo.lid_open()
        host.test_wait_for_resume(boot_id)

        info = self.pyauto.GetLoginInfo()
        logging.info(info)
        if not info['is_logged_in']:
            raise error.TestError(
                'User is no longer logged in after sleep/resume cycle.')
