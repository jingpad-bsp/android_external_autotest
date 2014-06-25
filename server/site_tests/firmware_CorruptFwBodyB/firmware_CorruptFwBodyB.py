# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_CorruptFwBodyB(FirmwareTest):
    """
    Servo based firmware body B corruption test.

    The expected behavior is different if the firmware preamble USE_RO_NORMAL
    flag is enabled. In the case USE_RO_NORMAL ON, the firmware corruption
    doesn't hurt the boot results since it boots the RO path directly and does
    not load and verify the RW firmware body. In the case USE_RO_NORMAL OFF,
    the RW firwmare B corruption will result booting the firmware A.
    """
    version = 1

    def initialize(self, host, cmdline_args, dev_mode=False):
        super(firmware_CorruptFwBodyB, self).initialize(host, cmdline_args)
        self.backup_firmware()
        self.setup_dev_mode(dev_mode)
        self.setup_usbkey(usbkey=False)

    def cleanup(self):
        self.restore_firmware()
        super(firmware_CorruptFwBodyB, self).cleanup()

    def run_once(self):
        RO_enabled = (self.faft_client.bios.get_preamble_flags('b') &
                      vboot.PREAMBLE_USE_RO_NORMAL)
        logging.info("Corrupt firmware body B.")
        self.check_state((self.checkers.crossystem_checker, {
                              'mainfw_act': 'A',
                              'tried_fwb': '0',
                              }))
        self.faft_client.bios.corrupt_body('b')
        self.reboot_warm()

        logging.info("Expected firmware A boot and set try_fwb flag.")
        self.check_state((self.checkers.crossystem_checker, {
                              'mainfw_act': 'A',
                              'tried_fwb': '0',
                              }))
        if self.fw_vboot2:
            self.faft_client.system.set_fw_try_next('B')
        else:
            self.faft_client.system.set_try_fw_b()
        self.reboot_warm()

        logging.info("If RO enabled, expected firmware B boot; otherwise, "
                     "still A boot since B is corrupted. Restore B later.")
        self.check_state((self.checkers.crossystem_checker, {
                              'mainfw_act': 'B' if RO_enabled else 'A',
                              'tried_fwb': '0' if self.fw_vboot2 else '1',
                              }))
        self.faft_client.bios.restore_body('b')
        if self.fw_vboot2:
            self.faft_client.system.set_fw_try_next('A')
        self.reboot_warm()

        logging.info("Final check and done.")
        self.check_state((self.checkers.crossystem_checker, {
                              'mainfw_act': 'A',
                              'tried_fwb': '0',
                              }))
