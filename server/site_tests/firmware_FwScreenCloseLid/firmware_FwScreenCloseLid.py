# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft_classes import FAFTSequence


class firmware_FwScreenCloseLid(FAFTSequence):
    """
    Servo based lid close triggered shutdown test during firmware screens.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image --test"). On runtime, this test triggers
    firmware screens (developer, remove, insert, yuck, to_norm screens),
    and then closes the lid in order to power the machine down.
    """
    version = 1


    def wait_second_screen_and_close_lid(self):
        """Wait and trigger TO_NORM or RECOVERY INSERT screen and close lid."""
        self.wait_fw_screen_and_trigger_recovery()
        self.wait_longer_fw_screen_and_close_lid()


    def wait_yuck_screen_and_close_lid(self):
        """Wait and trigger yuck screen and clod lid."""
        # Insert a corrupted USB stick. A yuck screen is expected.
        self.servo.switch_usbkey('dut')
        time.sleep(self.delay.load_usb)
        self.wait_longer_fw_screen_and_close_lid()


    def setup(self):
        super(firmware_FwScreenCloseLid, self).setup()
        if self.client_attr.has_lid:
            self.assert_test_image_in_usb_disk()
            self.setup_dev_mode(dev_mode=True)
            self.servo.switch_usbkey('host')
            usb_dev = self.servo.probe_host_usb_dev()
            # Corrupt the kernel of USB stick. It is needed for triggering a
            # yuck screen later.
            self.corrupt_usb_kernel(usb_dev)


    def cleanup(self):
        if self.client_attr.has_lid:
            self.servo.switch_usbkey('host')
            usb_dev = self.servo.probe_host_usb_dev()
            # Restore the kernel of USB stick which is corrupted on setup phase.
            self.restore_usb_kernel(usb_dev)
        super(firmware_FwScreenCloseLid, self).cleanup()


    def run_once(self):
        if not self.client_attr.has_lid:
            logging.info('This test does nothing on devices without lid.')
            return

        if self.client_attr.chrome_ec and not self.check_ec_capability(['lid']):
            raise error.TestNAError("TEST IT MANUALLY! Chrome EC can't control "
                    "lid on the device %s" % self.client_attr.platform)

        self.register_faft_sequence((
            {   # Step 1, expected dev mode and reboot.
                # When the next DEVELOPER SCREEN shown, close lid
                # to make DUT shutdown.
                'state_checker': (self.checkers.crossystem_checker, {
                    'devsw_boot': '1',
                    'mainfw_type': 'developer',
                }),
                'firmware_action': (self.run_shutdown_process,
                                    (self.wait_fw_screen_and_close_lid,
                                     self.servo.lid_open,
                                     self.wait_fw_screen_and_ctrl_d)),
            },
            {   # Step 2, reboot. When the developer screen shown, press
                # enter key to trigger either TO_NORM screen (new) or
                # RECOVERY INSERT screen (old). Then close lid to
                # make DUT shutdown.
                'state_checker': (self.checkers.crossystem_checker, {
                    'devsw_boot': '1',
                    'mainfw_type': 'developer',
                }),
                'firmware_action': (self.run_shutdown_process,
                                    (self.wait_second_screen_and_close_lid,
                                     self.servo.lid_open,
                                     self.wait_fw_screen_and_ctrl_d,
                                     0)),
            },
            {   # Step 3, request recovery boot. When the RECOVERY INSERT
                # screen shows, close lid to make DUT shutdown.
                'state_checker': (self.checkers.crossystem_checker, {
                    'devsw_boot': '1',
                    'mainfw_type': 'developer',
                }),
                'userspace_action':
                    (self.faft_client.system.request_recovery_boot),
                'firmware_action': (self.run_shutdown_process,
                                    (self.wait_longer_fw_screen_and_close_lid,
                                     self.servo.lid_open,
                                     self.wait_fw_screen_and_ctrl_d,
                                     0)),
            },
            {   # Step 4, request recovery boot again. When the recovery
                # insert screen shows, insert a corrupted USB and trigger
                # a YUCK SCREEN. Then close lid to make DUT shutdown.
                'state_checker': (self.checkers.crossystem_checker, {
                    'devsw_boot': '1',
                    'mainfw_type': 'developer',
                }),
                'userspace_action': (
                    self.faft_client.system.request_recovery_boot),
                'firmware_action': (self.run_shutdown_process,
                                    (self.wait_yuck_screen_and_close_lid,
                                     self.servo.lid_open,
                                     self.wait_fw_screen_and_ctrl_d,
                                     0)),
            },
            {   # Step 5, switch back to normal mode.
                'state_checker': (self.checkers.crossystem_checker, {
                    'devsw_boot': '1',
                    'mainfw_type': 'developer',
                }),
                'userspace_action': self.enable_normal_mode_and_reboot,
                'reboot_action': None,
            },
            {   # Step 6, expected normal mode and request recovery boot.
                # Because an USB stick is inserted, a RECOVERY REMOVE screen
                # shows. Close lid to make DUT shutdown.
                'state_checker': (self.checkers.crossystem_checker, {
                    'devsw_boot': '0',
                    'mainfw_type': 'normal',
                }),
                'userspace_action':
                    (self.faft_client.system.request_recovery_boot),
                'firmware_action': (self.run_shutdown_process,
                                    (self.wait_longer_fw_screen_and_close_lid,
                                     self.servo.lid_open,
                                     None,
                                     0)),
            },
            {   # Step 7, done.
                'state_checker': (self.checkers.crossystem_checker, {
                    'devsw_boot': '0',
                    'mainfw_type': 'normal',
                }),
            },
        ))
        self.run_faft_sequence()
