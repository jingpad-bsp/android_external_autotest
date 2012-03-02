# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
from autotest_lib.client.common_lib import error
from autotest_lib.server import test, utils
from autotest_lib.server.cros import servo

class platform_CloseOpenLidSimple(test.test):
    """Uses servo to send the host to sleep and wake back up.

    Uses pwr_button and lid_open gpios in various combinations.
    """
    version = 1


    def initialize(self, host):
        self.servo = servo.Servo.create_simple(host.hostname)
        self.host = host
        if not self.host.wait_up(timeout=30):
            raise error.TestError('DUT unavailable')


    def run_once(self):
        # lid only
        self.servo.lid_close()
        if utils.ping(self.host.ip, tries=5) == 0:
            raise error.TestFail('DUT did not sleep after lid close.')
        self.servo.lid_open()
        if not self.host.wait_up(timeout=30):
            raise error.TestFail('DUT did not wake on lid open.')


        # pwr_button and open lid
        self.servo.power_long_press()
        if utils.ping(self.host.ip, tries=5) == 0:
            raise error.TestFail('DUT did not power down on power long-press.')
        self.servo.lid_close()
        self.servo.lid_open()
        if not self.host.wait_up(timeout=30):
            raise error.TestFail('DUT did not boot on lid open.')
