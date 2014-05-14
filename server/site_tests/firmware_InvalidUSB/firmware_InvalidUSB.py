# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faft.firmware_test import ConnectionError
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_InvalidUSB(FirmwareTest):
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

    def initialize(self, host, cmdline_args):
        super(firmware_InvalidUSB, self).initialize(host, cmdline_args)
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
        logging.info("Turn on the recovery boot. Remove and insert the"
                     "corrupted USB stick, a boot failure is expected."
                     "Restore the USB image and boot it again.")
        self.check_state((self.checkers.crossystem_checker, {
                          'devsw_boot': '0',
                          'mainfw_type': 'normal',
                          }))
        self.faft_client.system.request_recovery_boot()
        self.reboot_warm(wait_for_dut_up=False)
        self.wait_fw_screen_and_plug_usb()
        logging.info('Wait to ensure the USB image is unable to boot...')
        try:
            self.wait_for_client()
            raise error.TestFail('Should not boot from the invalid USB image.')
        except ConnectionError:
            logging.info(
                'The USB image is surely unable to boot. Restore it and try...')

        self.restore_usb()
        time.sleep(self.faft_config.sync)
        self.servo.switch_usbkey('dut')
        self.wait_for_kernel_up(install_deps=True)

        logging.info("Expected to boot the restored USB image and reboot.")
        self.check_state((self.checkers.crossystem_checker, {
                          'mainfw_type': 'recovery',
                          'recovery_reason': vboot.RECOVERY_REASON['US_TEST'],
                          }))
        self.reboot_warm()

        logging.info("Expected to normal boot and done.")
        self.check_state((self.checkers.crossystem_checker, {
                          'devsw_boot': '0',
                          'mainfw_type': 'normal',
                          }))
