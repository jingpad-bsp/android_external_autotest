# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faft.firmware_test import ConnectionError
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_LegacyRecovery(FirmwareTest):
    """
    Servo based test to Verify recovery request at Remove Screen.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image --test"). It recovery boots to the USB image
    and sets recovery_request=1 and do a reboot. A failure is expected.
    """
    version = 1

    def initialize(self, host, cmdline_args):
        super(firmware_LegacyRecovery, self).initialize(host, cmdline_args)
        self.setup_usbkey(usbkey=True, host=False)
        self.setup_dev_mode(dev_mode=False)

    def cleanup(self):
        super(firmware_LegacyRecovery, self).cleanup()

    def run_once(self):
        logging.info("Turn on the recovery boot. Enable recovery request "
                     "and perform a reboot.")
        self.check_state((self.checkers.crossystem_checker, {
                           'devsw_boot': '0',
                           'mainfw_type': 'normal',
                           }))
        self.faft_client.system.request_recovery_boot()
        self.reboot_warm(wait_for_dut_up=False)
        self.wait_fw_screen_and_plug_usb()
        try:
            self.wait_for_client(install_deps=True)
        except ConnectionError:
            raise error.TestError('Failed to boot the USB image.')
        self.faft_client.system.run_shell_command(
                                   'crossystem recovery_request=1')

        logging.info("Wait to ensure no recovery boot at remove screen "
                     "and a boot failure is expected. "
                     "Unplug and plug USB, try to boot it again.")
        self.check_state((self.checkers.crossystem_checker, {
                           'mainfw_type': 'recovery',
                           }))
        self.reboot_warm(wait_for_dut_up=False)
        logging.info('Wait to ensure DUT doesnt Boot on USB at Remove screen.')
        try:
            self.wait_for_client()
            raise error.TestFail('Unexpected USB boot at Remove Screen.')
        except ConnectionError:
            logging.info('Done, Waited till timeout and no USB boot occured.')
        self.wait_fw_screen_and_plug_usb()
        self.wait_for_client()

        logging.info("Expected to boot the restored USB image and reboot.")
        self.check_state((self.checkers.crossystem_checker, {
                           'mainfw_type': 'recovery',
                           'recovery_reason': vboot.RECOVERY_REASON['LEGACY'],
                           }))
        self.reboot_warm()

        logging.info("Expected to normal boot and done.")
        self.check_state((self.checkers.crossystem_checker, {
                           'devsw_boot': '0',
                           'mainfw_type': 'normal',
                           }))
