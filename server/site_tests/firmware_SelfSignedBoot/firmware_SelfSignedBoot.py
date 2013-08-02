# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros import vboot_constants as vboot
from autotest_lib.server.cros.faft.faft_classes import FAFTSequence


class firmware_SelfSignedBoot(FAFTSequence):
    """
    Servo based developer mode boot only test to Self signed Kernels.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by 'build_image test'). On runtime, this test first switches
    DUT to dev mode. When dev_boot_usb=1 and dev_boot_signed_only=1, pressing
    Ctrl-U on developer screen should not boot the USB disk(recovery mode boot
    should work), and when USB image is resigned with SSD keys, pressing Ctrl-U
    should boot to the USB disk.
    """
    version = 1


    def setup(self, ec_wp=None):
        super(firmware_SelfSignedBoot, self).setup(ec_wp=ec_wp)
        self.setup_dev_mode(dev_mode=True)
        self.setup_usbkey(usbkey=True, host=False)

        self.original_dev_boot_usb = self.faft_client.system.get_dev_boot_usb()
        logging.info('Original dev_boot_usb value: %s',
                     str(self.original_dev_boot_usb))

        self.usb_dev = self.get_dut_usb_dev()
        if not self.usb_dev:
            raise error.TestError("Unable to find USB disk")


    def cleanup(self):
        self.faft_client.system.set_dev_boot_usb(self.original_dev_boot_usb)
        self.disable_crossystem_selfsigned()
        self.ensure_internal_device_boot()
        self.resignimage_recoverykeys()
        super(firmware_SelfSignedBoot, self).cleanup()


    def ensure_internal_device_boot(self):
        """Ensure internal device boot; if not, reboot into it.

        If not, it may be a test failure during step 3 or 5, try to reboot
        and press Ctrl-D to internal device boot.
        """
        if self.faft_client.system.is_removable_device_boot():
            logging.info('Reboot into internal disk...')
            self.run_faft_step({
                'firmware_action': self.wait_fw_screen_and_ctrl_d,
            })


    def try_ctrl_u_and_ctrl_d(self):
        """Try to press Ctrl-U first and then press Ctrl-D"""
        self.wait_fw_screen_and_ctrl_u()
        # If the above Ctrl-U doesn't work, the firmware beeps twice.
        # Should wait the beep done before pressing Ctrl-D.
        time.sleep(self.delay.beep)
        self.press_ctrl_d()


    def resignimage_ssdkeys(self):
        """Re-signing the USB image using the SSD keys."""
        self.faft_client.system.run_shell_command(
            '/usr/share/vboot/bin/make_dev_ssd.sh -i %s' % self.usb_dev)


    def resignimage_recoverykeys(self):
        """Re-signing the USB image using the Recovery keys."""
        self.faft_client.system.run_shell_command(
            '/usr/share/vboot/bin/make_dev_ssd.sh -i %s --recovery_key'
            % self.usb_dev)


    def enable_crossystem_selfsigned(self):
        """Enable dev_boot_signed_only + dev_boot_usb."""
        self.faft_client.system.run_shell_command(
            'crossystem dev_boot_signed_only=1')
        self.faft_client.system.run_shell_command('crossystem dev_boot_usb=1')


    def disable_crossystem_selfsigned(self):
        """Disable dev_boot_signed_only + dev_boot_usb."""
        self.faft_client.system.run_shell_command(
            'crossystem dev_boot_signed_only=0')
        self.faft_client.system.run_shell_command('crossystem dev_boot_usb=0')


    def run_once(self):
        if (self.client_attr.has_keyboard and
                not self.check_ec_capability(['keyboard'])):
            raise error.TestNAError("TEST IT MANUALLY! This test can't be "
                                  "automated on non-Chrome-EC devices.")
        # The old models need users to remove and insert USB stick during boot.
        remove_usb = (self.faft_client.system.get_platform_name() in
                     ('Mario', 'Alex', 'ZGB', 'Aebl', 'Kaen'))
        self.register_faft_sequence((
            {   # Step 1, expected developer mode, set dev_boot_usb and
                # dev_boot_signed_only to 1.
                'state_checker': (self.checkers.dev_boot_usb_checker, False),
                'userspace_action': self.enable_crossystem_selfsigned,
                'firmware_action': self.try_ctrl_u_and_ctrl_d,
                'install_deps_after_boot': True,
            },
            {   # Step 2, expected internal disk boot, switch to recovery mode.
                'state_checker': (self.checkers.dev_boot_usb_checker, False,
                    'Not internal disk boot, dev_boot_usb misbehaved'),
                'userspace_action': self.enable_rec_mode_and_reboot,
                'reboot_action': None,
                'firmware_action': None,
                'install_deps_after_boot': True,
            },
            {   # Step 3, expected recovery boot and reboot.
                'state_checker': (self.checkers.crossystem_checker, {
                    'mainfw_type': 'recovery',
                    'recovery_reason' : vboot.RECOVERY_REASON['RO_MANUAL'],
                }),
                 'firmware_action': self.wait_fw_screen_and_ctrl_d,
            },
            {   # Step 4, expected internal disk boot, resign with SSD keys.
                'state_checker': (self.checkers.dev_boot_usb_checker, False,
                    'Not internal disk boot, dev_boot_usb misbehaved'),
                'userspace_action': self.resignimage_ssdkeys,
                'firmware_action': self.wait_fw_screen_and_ctrl_u,
                'install_deps_after_boot': True,
            },
            {   # Step 5, expected USB boot.
                'state_checker': (self.checkers.dev_boot_usb_checker, True,
                    'Not USB boot, Ctrl-U not work'),
                'firmware_action': self.wait_fw_screen_and_ctrl_d,
            },
            {   # Step 6, done.
                'state_checker': (self.checkers.dev_boot_usb_checker, False),
            }
        ))
        self.run_faft_sequence()
