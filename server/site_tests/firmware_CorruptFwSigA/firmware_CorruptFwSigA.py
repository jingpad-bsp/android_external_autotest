# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_CorruptFwSigA(FirmwareTest):
    """
    Servo based firmware signature A corruption test.
    """
    version = 1

    def initialize(self, host, cmdline_args, dev_mode=False):
        super(firmware_CorruptFwSigA, self).initialize(host, cmdline_args)
        self.backup_firmware()
        self.setup_dev_mode(dev_mode)
        self.setup_usbkey(usbkey=False)

    def cleanup(self):
        self.restore_firmware()
        super(firmware_CorruptFwSigA, self).cleanup()

    def run_once(self):
        logging.info("Corrupt firmware signature A.")
        self.check_state((self.checkers.fw_tries_checker, 'A'))
        self.faft_client.bios.corrupt_sig('a')
        self.reboot_warm()

        logging.info("Expected firmware B boot and set fwb_tries flag.")
        self.check_state((self.checkers.fw_tries_checker, ('B', False)))

        self.try_fwb()
        self.reboot_warm()

        logging.info("Still expected firmware B boot and restore firmware A.")
        self.check_state((self.checkers.fw_tries_checker, 'B'))
        self.faft_client.bios.restore_sig('a')
        self.reboot_warm()

        expected_slot = 'B' if self.fw_vboot2 else 'A'
        logging.info("Expected firmware " + expected_slot + " boot, done.")
        self.check_state((self.checkers.fw_tries_checker, expected_slot))
