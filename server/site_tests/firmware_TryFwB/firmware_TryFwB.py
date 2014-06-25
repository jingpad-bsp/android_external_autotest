# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_TryFwB(FirmwareTest):
    """
    Servo based RW firmware B boot test.
    """
    version = 1

    def initialize(self, host, cmdline_args, dev_mode=False, ec_wp=None):
        super(firmware_TryFwB, self).initialize(host, cmdline_args, ec_wp=ec_wp)
        self.setup_dev_mode(dev_mode)
        self.setup_usbkey(usbkey=False)
        if not self.fw_vboot2:
            self.setup_tried_fwb(tried_fwb=False)

    def cleanup(self):
        self.setup_tried_fwb(tried_fwb=False)
        super(firmware_TryFwB, self).cleanup()

    def run_once(self):
        logging.info("Set fwb_tries flag")
        self.check_state((self.checkers.crossystem_checker, {
                          'mainfw_act': 'A',
                          'tried_fwb': '0',
                          }))
        if self.fw_vboot2:
            self.faft_client.system.set_fw_try_next('B')
        else:
            self.faft_client.system.set_try_fw_b()
        self.reboot_warm()

        logging.info("Expected firmware B boot, reboot")
        self.check_state((self.checkers.crossystem_checker, {
                          'mainfw_act': 'B',
                          'tried_fwb': '0' if self.fw_vboot2 else '1',
                          }))
        if self.fw_vboot2:
            self.faft_client.system.set_fw_try_next('A')
        self.reboot_warm()

        logging.info("Expected firmware A boot, done")
        self.check_state((self.checkers.crossystem_checker, {
                          'mainfw_act': 'A',
                          'tried_fwb': '0',
                          }))
