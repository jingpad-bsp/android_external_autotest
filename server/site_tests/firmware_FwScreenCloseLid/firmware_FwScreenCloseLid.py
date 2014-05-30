# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_FwScreenCloseLid(FirmwareTest):
    """
    Servo based lid close triggered shutdown test during firmware screens.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image --test"). On runtime, this test triggers
    firmware screens (developer, remove, insert, yuck, to_norm screens),
    and then closes the lid in order to power the machine down.
    """
    version = 1

    SHORT_SHUTDOWN_CONFIRMATION_PERIOD = 0.1

    def wait_second_screen_and_close_lid(self):
        """Wait and trigger TO_NORM or RECOVERY INSERT screen and close lid."""
        self.wait_fw_screen_and_trigger_recovery()
        self.wait_longer_fw_screen_and_close_lid()

    def wait_yuck_screen_and_close_lid(self):
        """Wait and trigger yuck screen and clod lid."""
        # Insert a corrupted USB stick. A yuck screen is expected.
        self.servo.switch_usbkey('dut')
        time.sleep(self.faft_config.load_usb)
        self.wait_longer_fw_screen_and_close_lid()

    def initialize(self, host, cmdline_args):
        super(firmware_FwScreenCloseLid, self).initialize(host, cmdline_args)
        if self.faft_config.has_lid:
            self.assert_test_image_in_usb_disk()
            self.setup_dev_mode(dev_mode=True)
            self.servo.switch_usbkey('host')
            usb_dev = self.servo.probe_host_usb_dev()
            # Corrupt the kernel of USB stick. It is needed for triggering a
            # yuck screen later.
            self.corrupt_usb_kernel(usb_dev)

    def cleanup(self):
        if self.faft_config.has_lid:
            self.servo.switch_usbkey('host')
            usb_dev = self.servo.probe_host_usb_dev()
            # Restore kernel of USB stick which is corrupted on setup phase.
            self.restore_usb_kernel(usb_dev)
        super(firmware_FwScreenCloseLid, self).cleanup()

    def run_once(self):
        if not self.faft_config.has_lid:
            logging.info('This test does nothing on devices without lid.')
            return

        if self.faft_config.chrome_ec and not self.check_ec_capability(['lid']):
            raise error.TestNAError("TEST IT MANUALLY! ChromeEC can't control "
                                    "lid on the device %s" %
                                    self.faft_config.platform)

        logging.info("Expected dev mode and reboot. "
                     "When the next DEVELOPER SCREEN shown, close lid "
                     "to make DUT shutdown.")
        self.check_state((self.checkers.crossystem_checker, {
                          'devsw_boot': '1',
                          'mainfw_type': 'developer',
                          }))
        self.reboot_warm(wait_for_dut_up=False)
        self.run_shutdown_process(self.wait_fw_screen_and_close_lid,
                                  self.servo.lid_open,
                                  self.wait_fw_screen_and_ctrl_d)
        self.wait_for_kernel_up()

        logging.info("Reboot. When the developer screen shown, press "
                     "enter key to trigger either TO_NORM screen (new) or "
                     "RECOVERY INSERT screen (old). Then close lid to "
                     "make DUT shutdown.")
        self.check_state((self.checkers.crossystem_checker, {
                          'devsw_boot': '1',
                          'mainfw_type': 'developer',
                          }))
        self.reboot_warm(wait_for_dut_up=False)
        self.run_shutdown_process(self.wait_second_screen_and_close_lid,
                                  self.servo.lid_open,
                                  self.wait_fw_screen_and_ctrl_d,
                                  self.SHORT_SHUTDOWN_CONFIRMATION_PERIOD)
        self.wait_for_kernel_up()

        logging.info("Request recovery boot. When the RECOVERY INSERT "
                     "screen shows, close lid to make DUT shutdown.")
        self.check_state((self.checkers.crossystem_checker, {
                          'devsw_boot': '1',
                          'mainfw_type': 'developer',
                          }))
        self.faft_client.system.request_recovery_boot()
        self.reboot_warm(wait_for_dut_up=False)
        self.run_shutdown_process(self.wait_longer_fw_screen_and_close_lid,
                                  self.servo.lid_open,
                                  self.wait_fw_screen_and_ctrl_d,
                                  self.SHORT_SHUTDOWN_CONFIRMATION_PERIOD)
        self.wait_for_kernel_up()

        logging.info("Request recovery boot again. When the recovery "
                     "insert screen shows, insert a corrupted USB and trigger "
                     "a YUCK SCREEN. Then close lid to make DUT shutdown.")
        self.check_state((self.checkers.crossystem_checker, {
                          'devsw_boot': '1',
                          'mainfw_type': 'developer',
                          }))
        self.faft_client.system.request_recovery_boot()
        self.reboot_warm(wait_for_dut_up=False)
        self.run_shutdown_process(self.wait_yuck_screen_and_close_lid,
                                  self.servo.lid_open,
                                  self.wait_fw_screen_and_ctrl_d,
                                  self.SHORT_SHUTDOWN_CONFIRMATION_PERIOD)
        self.wait_for_kernel_up()

        logging.info("Switch back to normal mode.")
        self.check_state((self.checkers.crossystem_checker, {
                          'devsw_boot': '1',
                          'mainfw_type': 'developer',
                          }))
        self.enable_normal_mode_and_reboot()

        logging.info("Expected normal mode and request recovery boot. "
                     "Because an USB stick is inserted, a RECOVERY REMOVE "
                     "screen shows. Close lid to make DUT shutdown.")
        self.check_state((self.checkers.crossystem_checker, {
                          'devsw_boot': '0',
                          'mainfw_type': 'normal',
                          }))
        self.faft_client.system.request_recovery_boot()
        self.reboot_warm(wait_for_dut_up=False)
        self.run_shutdown_process(self.wait_longer_fw_screen_and_close_lid,
                                  self.servo.lid_open,
                                  None,
                                  self.SHORT_SHUTDOWN_CONFIRMATION_PERIOD)
        self.wait_for_kernel_up()
        self.check_state((self.checkers.crossystem_checker, {
                          'devsw_boot': '0',
                          'mainfw_type': 'normal',
                          }))
