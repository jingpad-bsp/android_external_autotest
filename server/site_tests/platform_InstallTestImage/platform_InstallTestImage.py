# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.server import test

class platform_InstallTestImage(test.test):
    """Installs a specified test image onto a servo-connected DUT."""
    version = 1

    # Time to allow for chromeos-install.  At the time of this
    # writing, four minutes is about double what's needed.
    _INSTALL_TIMEOUT = 240

    def run_once(self, host, image):
        host.servo.install_recovery_image(image)
        if not host.wait_up(timeout=host.USB_BOOT_TIMEOUT):
            raise error.TestFail('DUT failed to boot from USB'
                                 ' after %d seconds' % host.USB_BOOT_TIMEOUT)
        host.run('chromeos-install --yes ; halt',
                 timeout=self._INSTALL_TIMEOUT)
        host.servo.power_long_press()
        host.servo.set('usb_mux_sel1', 'servo_sees_usbkey')
        host.servo.power_short_press()
        if not host.wait_up(timeout=host.BOOT_TIMEOUT):
            raise error.TestFail('DUT failed to reboot installed test image'
                                 ' after %d seconds' % host.BOOT_TIMEOUT)
