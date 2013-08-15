# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft.faft_classes import FAFTSequence


class firmware_DevBootUSB(FAFTSequence):
    """
    Servo based Ctrl-U developer USB boot test.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image test"). On runtime, this test first switches
    DUT to developer mode. When dev_boot_usb=0, pressing Ctrl-U on developer
    screen should not boot the USB disk. When dev_boot_usb=1, pressing Ctrl-U
    should boot the USB disk.
    """
    version = 1


    def setup(self, ec_wp=None):
        super(firmware_DevBootUSB, self).setup(ec_wp=ec_wp)
        self.setup_dev_mode(dev_mode=True)
        self.setup_usbkey(usbkey=True, host=False)

        self.original_dev_boot_usb = self.faft_client.system.get_dev_boot_usb()
        logging.info('Original dev_boot_usb value: %s',
                     str(self.original_dev_boot_usb))


    def cleanup(self):
        self.ensure_internal_device_boot()
        super(firmware_DevBootUSB, self).cleanup()


    def try_ctrl_u_and_ctrl_d(self):
        """Try to press Ctrl-U first and then press Ctrl-D"""
        self.wait_fw_screen_and_ctrl_u()
        # If the above Ctrl-U doesn't work, the firmware beeps twice.
        # Should wait the beep done before pressing Ctrl-D.
        time.sleep(self.faft_config.beep)
        self.press_ctrl_d()


    def ensure_internal_device_boot(self):
        """Ensure internal device boot; if not, reboot into it.

        If not, it may be a test failure during step 2 or 3, try to reboot
        and press Ctrl-D to internal device boot.
        """
        if self.faft_client.system.is_removable_device_boot():
            logging.info('Reboot into internal disk...')
            self.run_faft_step({
                'userspace_action': (self.faft_client.system.set_dev_boot_usb,
                                     self.original_dev_boot_usb),
                'firmware_action': self.wait_fw_screen_and_ctrl_d,
            })


    def run_once(self):
        if (self.faft_config.has_keyboard and
                not self.check_ec_capability(['keyboard'])):
            raise error.TestNAError("TEST IT MANUALLY! This test can't be "
                    "automated on non-Chrome-EC devices.")

        self.register_faft_sequence((
            {   # Step 1, expected developer mode, set dev_boot_usb to 0
                'state_checker': (self.checkers.dev_boot_usb_checker, False),
                'userspace_action': (self.faft_client.system.set_dev_boot_usb,
                                     0),
                # Ctrl-U doesn't take effect as dev_boot_usb=0.
                # Falls back to Ctrl-D internal disk boot.
                'firmware_action': self.try_ctrl_u_and_ctrl_d,
                'install_deps_after_boot': True,
            },
            {   # Step 2, expected internal disk boot, set dev_boot_usb to 1
                'state_checker': (self.checkers.dev_boot_usb_checker, False,
                        "Not internal disk boot, dev_boot_usb misbehaved"),
                'userspace_action': (self.faft_client.system.set_dev_boot_usb,
                                     1),
                'firmware_action': self.wait_fw_screen_and_ctrl_u,
                'install_deps_after_boot': True,
            },
            {   # Step 3, expected USB boot, set dev_boot_usb to the original
                'state_checker': (self.checkers.dev_boot_usb_checker, True,
                        "Not USB boot, Ctrl-U not work"),
                'userspace_action': (self.faft_client.system.set_dev_boot_usb,
                                     self.original_dev_boot_usb),
                'firmware_action': self.wait_fw_screen_and_ctrl_d,
            },
            {   # Step 4, done
                'state_checker': (self.checkers.dev_boot_usb_checker, False),
            }
        ))
        self.run_faft_sequence()
