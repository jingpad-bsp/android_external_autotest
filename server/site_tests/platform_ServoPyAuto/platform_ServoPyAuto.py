# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

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
        self.servo.lid_close()
        self.assert_pingfail()
        self.servo.lid_open()
        self.wait_for_client()

        info = self.pyauto.GetLoginInfo()
        logging.info(info)
        assert info['is_logged_in'], 'User is not logged in.'
