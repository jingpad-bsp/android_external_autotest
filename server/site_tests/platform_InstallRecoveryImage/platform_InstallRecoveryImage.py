# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server import test

class platform_InstallRecoveryImage(test.test):
    """Installs a specified recovery image onto a servo-connected DUT."""
    version = 1

    def run_once(self, host, image):
        host.servo.install_recovery_image(image,
                                          make_image_noninteractive=True,
                                          host=host)

        # Verify we can ping the machine afterwards.
        # TODO(sosa): Add a better test of valid image recovery.
        host.test_wait_for_boot()
