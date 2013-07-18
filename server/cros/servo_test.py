# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server import test


class ServoTest(test.test):
    """ServoTest: a test subclassing it requires Servo board connected.

    It checks the servo connectivity on initialization.
    """
    version = 3

    def initialize(self, host):
        """Create a Servo object and initialize it."""
        self.servo = host.servo
        self.servo.initialize_dut()

    # TODO(waihong): Record the servo logs.
