# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

import autotest_lib.server.cros.servotest

class platform_LongPressPower(autotest_lib.server.cros.servotest.ServoTest):
    """Uses servo pwr_button gpio to power the host off and back on.
    """
    version = 1

    def run_once(self, host):
        # ensure host starts in a good state
        self.assert_ping()
        # turn off device
        self.servo.power_long_press()
        # ensure host is now off
        self.assert_pingfail()
        # ensure host boots
        self.servo.boot_devmode()
        self.assert_ping()
