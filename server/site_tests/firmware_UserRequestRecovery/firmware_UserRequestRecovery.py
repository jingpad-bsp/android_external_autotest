# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_UserRequestRecovery(FAFTSequence):
    """
    Servo based user request recovery boot test.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image --test"). On runtime, this test first requests
    a recovery mode on next boot by setting the crossystem recovery_request
    flag. It then triggers recovery mode by unplugging and plugging in the USB
    disk and checks success of it.
    """
    version = 1

    # Code dedicated for user triggering recovery mode through crossystem.
    USER_RECOVERY_REQUEST_CODE = '193'


    def ensure_normal_boot(self):
        """Ensure normal mode boot this time.

        If not, it may be a test failure during step 2, try to recover to
        normal mode by simply rebooting the machine.
        """
        if self.crossystem_checker({'mainfw_type': 'recovery'}):
            self.sync_and_hw_reboot()
            self.wait_for_client_offline()
            self.wait_for_client()


    def setup(self):
        super(firmware_UserRequestRecovery, self).setup()
        self.assert_test_image_in_usb_disk()
        self.servo.set('usb_mux_sel1', 'dut_sees_usbkey')
        self.setup_dev_mode(dev_mode=False)


    def cleanup(self):
        self.ensure_normal_boot()
        super(firmware_UserRequestRecovery, self).cleanup()


    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step 1, request recovery boot
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': 'normal',
                    'recoverysw_boot': '0',
                }),
                'userspace_action': self.faft_client.request_recovery_boot,
                'firmware_action': self.wait_and_plug_usb,
                'install_deps_after_boot': True,
            },
            {   # Step 2, expected recovery boot
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': 'recovery',
                    'recovery_reason' : self.USER_RECOVERY_REQUEST_CODE,
                    'recoverysw_boot': '0',
                }),
            },
            {   # Step 3, expected normal boot
                'state_checker': (self.crossystem_checker, {
                    'mainfw_type': 'normal',
                    'recoverysw_boot': '0',
                }),
            },
        ))
        self.run_faft_sequence()


    def wait_and_plug_usb(self):
        """Wait for firmware warning screen and then unplug and plug the USB."""
        time.sleep(self.FIRMWARE_SCREEN_DELAY)
        self.servo.set('usb_mux_sel1', 'servo_sees_usbkey')
        time.sleep(self.USB_PLUG_DELAY)
        self.servo.set('usb_mux_sel1', 'dut_sees_usbkey')
