# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros import servo_test

class platform_InstallRecoveryImage(servo_test.ServoTest):
    """Installs a specified recovery image onto a servo-connected DUT."""
    version = 1

    def run_once(self, host, image, usb):
        self.servo.install_recovery_image(image, usb)
        # Verify we can ping the machine afterwards.
        # TODO(sosa): Add a better test of valid image recovery.
        self.assert_ping()
