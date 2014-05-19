# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_DevMode(FirmwareTest):
    """
    Servo based developer firmware boot test.
    """
    version = 1

    def initialize(self, host, cmdline_args, ec_wp=None):
        super(firmware_DevMode, self).initialize(host, cmdline_args,
                                                 ec_wp=ec_wp)
        self.setup_dev_mode(dev_mode=False)
        self.setup_usbkey(usbkey=False)

    def cleanup(self):
        self.setup_dev_mode(dev_mode=False)
        super(firmware_DevMode, self).cleanup()

    def run_once(self):
        logging.info("Enable dev mode.")
        self.check_state((self.checkers.crossystem_checker, {
                              'devsw_boot': '0',
                              'mainfw_type': 'normal',
                              }))
        self.enable_dev_mode_and_reboot()
        self.wait_dev_screen_and_ctrl_d()
        self.wait_for_client()

        logging.info("Expected developer mode boot and enable normal mode.")
        self.check_state((self.checkers.crossystem_checker, {
                              'devsw_boot': '1',
                              'mainfw_type': 'developer',
                              }))
        self.enable_normal_mode_and_reboot()
        self.wait_for_client()

        logging.info("Expected normal mode boot, done.")
        self.check_state((self.checkers.crossystem_checker, {
                              'devsw_boot': '0',
                              'mainfw_type': 'normal',
                              }))
