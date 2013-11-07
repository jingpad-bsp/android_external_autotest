# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faft.faft_classes import ConnectionError
from autotest_lib.server.cros.faft.faft_classes import FAFTSequence


class firmware_LegacyRecovery(FAFTSequence):
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


    def plug_usb_enable_recovery_request(self):
        """Wait and plug USB at recovery screen.
           Set crossystem recovery_request to 1.
        """
        self.wait_fw_screen_and_plug_usb()
        try:
            self.wait_for_client(install_deps=True)
        except ConnectionError:
            raise error.TestError('Failed to boot the USB image.')
        self.faft_client.system.run_shell_command(
            'crossystem recovery_request=1')


    def ensure_no_recovery_and_replug_usb(self):
        """Wait to ensure DUT doesnt boot at recovery remove screen.
           Unplug and plug USB.
        """
        logging.info('Wait to ensure DUT doesnt Boot on USB at Remove screen.')
        try:
            self.wait_for_client()
            raise error.TestFail('Unexpected USB boot at Remove Screen.')
        except ConnectionError:
            logging.info('Done, Waited till timeout and no USB boot occured.')

        self.wait_fw_screen_and_plug_usb()


    def run_once(self):
        self.register_faft_sequence((
            {   # Step 1, turn on the recovery boot. Enable recovery request
                # and perform a reboot.
                'state_checker': (self.checkers.crossystem_checker, {
                    'devsw_boot': '0',
                    'mainfw_type': 'normal',
                }),
                'userspace_action':
                    (self.faft_client.system.request_recovery_boot),
                'firmware_action': self.plug_usb_enable_recovery_request,
                'install_deps_after_boot': True,
            },
            {   # Step 2, wait to ensure no recovery boot at remove screen
                # and a boot failure is expected.
                # Unplug and plug USB, try to boot it again.
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_type': 'recovery',
                }),
                'firmware_action': self.ensure_no_recovery_and_replug_usb,
            },
            {   # Step 3, expected to boot the restored USB image and reboot.
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_type': 'recovery',
                    'recovery_reason' : vboot.RECOVERY_REASON['LEGACY'],
                }),
            },
            {   # Step 4, expected to normal boot and done.
                'state_checker': (self.checkers.crossystem_checker, {
                    'devsw_boot': '0',
                    'mainfw_type': 'normal',
                }),
            },
        ))
        self.run_faft_sequence()
