# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faft.faft_classes import FAFTSequence


class firmware_InvalidUSB(FAFTSequence):
    """
    Servo based booting an invalid USB image test.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image --test"). On runtime, this test corrupts the
    USB image and tries to boot into it. A failure is expected. It then
    restores the USB image and boots into it again.
    """
    version = 1


    def restore_usb(self):
        """Restore the USB image. USB plugs/unplugs happen in this method."""
        self.servo.switch_usbkey('host')
        usb_dev = self.servo.probe_host_usb_dev()
        self.restore_usb_kernel(usb_dev)


    def insert_corrupted_usb_and_restore(self):
        """Insert the corrupted USB on firmware screen. Then restore it."""
        self.wait_fw_screen_and_plug_usb()
        logging.info('Wait to ensure the USB image is unable to boot...')
        try:
            self.wait_for_client()
            raise error.TestFail('Should not boot from the invalid USB image.')
        except AssertionError:
            logging.info(
                'The USB image is surely unable to boot. Restore it and try...')

        self.restore_usb()
        time.sleep(self.delay.sync)
        self.servo.switch_usbkey('dut')


    def setup(self):
        super(firmware_InvalidUSB, self).setup()
        self.servo.switch_usbkey('host')
        usb_dev = self.servo.probe_host_usb_dev()
        self.assert_test_image_in_usb_disk(usb_dev)
        self.corrupt_usb_kernel(usb_dev)
        self.setup_dev_mode(dev_mode=False)
        self.servo.switch_usbkey('dut')


    def cleanup(self):
        self.restore_usb()
        super(firmware_InvalidUSB, self).cleanup()


    def run_once(self):
        self.register_faft_sequence((
            {   # Step 1, turn on the recovery boot. Remove and insert the
                # corrupted USB stick, a boot failure is expected.
                # Restore the USB image and boot it again.
                'state_checker': (self.checkers.crossystem_checker, {
                    'devsw_boot': '0',
                    'mainfw_type': 'normal',
                }),
                'userspace_action':
                    (self.faft_client.system.request_recovery_boot),
                'firmware_action': self.insert_corrupted_usb_and_restore,
                'install_deps_after_boot': True,
            },
            {   # Step 2, expected to boot the restored USB image and reboot.
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_type': 'recovery',
                    'recovery_reason' : vboot.RECOVERY_REASON['US_TEST'],
                }),
            },
            {   # Step 3, expected to normal boot and done.
                'state_checker': (self.checkers.crossystem_checker, {
                    'devsw_boot': '0',
                    'mainfw_type': 'normal',
                }),
            },
        ))
        self.run_faft_sequence()
