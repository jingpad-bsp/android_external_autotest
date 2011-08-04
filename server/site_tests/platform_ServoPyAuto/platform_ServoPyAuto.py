# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import shutil
import sys
import time
from autotest_lib.server import test, autotest
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
import autotest_lib.server.cros.servotest

class platform_ServoPyAuto(autotest_lib.server.cros.servotest.ServoTest):
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
