# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_DevTriggerRecovery(FirmwareTest):
    """
    Servo based recovery boot test triggered by pressing enter at dev screen.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image --test"). On runtime, this test changes dev
    switch and reboot. It then presses the enter key at dev warning screen to
    trigger recovery boot and checks the success of it.
    """
    version = 1

    def initialize(self, host, cmdline_args):
        """Initialize the test"""
        super(firmware_DevTriggerRecovery, self).initialize(host, cmdline_args)
        self.switcher.setup_mode('normal')
        self.setup_usbkey(usbkey=True, host=False)

    def run_once(self):
        """Main test logic"""
        if self.faft_config.mode_switcher_type != 'physical_button_switcher':
            raise error.TestNAError('This test is only valid in physical button'
                                    'controlled dev mode firmware.')

        logging.info("Enable dev mode.")
        self.check_state((self.checkers.crossystem_checker, {
                              'devsw_boot': '0',
                              'mainfw_act': 'A',
                              'mainfw_type': 'normal',
                              }))
        self.servo.enable_development_mode()
        self.switcher.mode_aware_reboot(wait_for_dut_up=False)
        self.switcher.bypass_dev_mode()
        self.switcher.wait_for_client()

        logging.info("Expected values based on platforms (see above), "
                     "run 'chromeos-firmwareupdate --mode todev && reboot', "
                     "and trigger recovery boot at dev screen. ")
        self.check_state((self.checkers.crossystem_checker, {
                    'devsw_boot': '1',
                    'mainfw_act': 'A',
                    'mainfw_type': 'developer',
                    }))
        self.faft_client.system.run_shell_command(
                 'chromeos-firmwareupdate --mode todev && reboot')
        # Ignore the default reboot_action here because the
        # userspace_action (firmware updater) will reboot the system.
        self.switcher.trigger_dev_to_rec()
        self.switcher.wait_for_client()

        logging.info("Expected recovery boot and disable dev switch.")
        self.check_state((self.checkers.crossystem_checker, {
                     'devsw_boot': '1',
                     'mainfw_type': 'recovery',
                     'recovery_reason' : vboot.RECOVERY_REASON['RW_DEV_SCREEN'],
                     }))
        self.servo.disable_development_mode()
        self.switcher.mode_aware_reboot()

        logging.info("Expected values based on platforms (see above), "
                     "and run 'chromeos-firmwareupdate --mode tonormal && "
                     "reboot'")
        self.check_state((self.checkers.crossystem_checker, {
                    'devsw_boot': '0',
                    'mainfw_act': 'A',
                    'mainfw_type': 'normal',
                    }))
        self.faft_client.system.run_shell_command(
                            'chromeos-firmwareupdate --mode tonormal && reboot')
        self.switcher.wait_for_client()

        logging.info("Expected normal mode boot, done.")
        self.check_state((self.checkers.crossystem_checker, {
                              'devsw_boot': '0',
                              'mainfw_act': 'A',
                              'mainfw_type': 'normal',
                              }))
