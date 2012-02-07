# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.server.cros.faftsequence import FAFTSequence


class firmware_FwScreenPressPower(FAFTSequence):
    """
    Servo based power button triggered shutdown test during firmware screens.

    This test requires a USB disk plugged-in, which contains a Chrome OS test
    image (built by "build_image --test"). On runtime, this test triggers
    four firmware screens (developer, remove, insert, and yuck screens), and
    then presses the power button in order to power the machine down.
    """
    version = 1


    def wait_insert_screen_and_press_power(self):
        """Wait and trigger recovery insert screen and press power button."""
        self.wait_fw_screen_and_trigger_recovery()
        self.wait_fw_screen_and_press_power()


    def wait_yuck_screen_and_press_power(self):
        """Wait and trigger yuck screen and press power button."""
        self.wait_fw_screen_and_trigger_recovery()
        # Insert a corrupted USB stick. A yuck screen is expected.
        # This USB stick will be removed in cleanup phase.
        time.sleep(self.USB_LOAD_DELAY)
        self.servo.set('usb_mux_sel1', 'dut_sees_usbkey')
        self.wait_fw_screen_and_press_power()


    def setup(self):
        super(firmware_FwScreenPressPower, self).setup()
        self.setup_dev_mode(dev_mode=False)
        self.servo.set('usb_mux_sel1', 'servo_sees_usbkey')
        usb_dev = self.servo.probe_host_usb_dev()
        # Corrupt the kernel of USB stick. It is needed for triggering a
        # yuck screen later.
        self.corrupt_usb_kernel(usb_dev)


    def cleanup(self):
        self.servo.set('usb_mux_sel1', 'servo_sees_usbkey')
        usb_dev = self.servo.probe_host_usb_dev()
        # Restore the kernel of USB stick which is corrupted on setup phase.
        self.restore_usb_kernel(usb_dev)
        super(firmware_FwScreenPressPower, self).cleanup()


    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step 1, enable dev mode and dev firmware. When the developer
                # screen shown, press power button to make DUT shutdown.
                'state_checker': (self.crossystem_checker, {
                    'devsw_boot': '0',
                    'mainfw_type': 'normal',
                    'recoverysw_boot': '0',
                }),
                'userspace_action': self.enable_dev_mode_and_fw,
                'reboot_action': None,
                'firmware_action': (self.run_shutdown_process,
                                    self.wait_fw_screen_and_press_power,
                                    None,
                                    self.wait_fw_screen_and_ctrl_d),
            },
            {   # Step 2, reboot. When the developer screen shown, press
                # enter key to trigger recovery insert screen. Then press
                # power button to make DUT shutdown.
                'state_checker': (self.crossystem_checker, {
                    'devsw_boot': '1',
                    'mainfw_type': 'developer',
                    'recoverysw_boot': '0',
                }),
                'firmware_action': (self.run_shutdown_process,
                                    self.wait_insert_screen_and_press_power,
                                    None,
                                    self.wait_fw_screen_and_ctrl_d),
            },
            {   # Step 3, reboot. When the developer screen shown, press
                # enter key and insert a corrupted USB stick to trigger
                # yuck screen. Then press power button to make DUT shutdown.
                'state_checker': (self.crossystem_checker, {
                    'devsw_boot': '1',
                    'mainfw_type': 'developer',
                    'recoverysw_boot': '0',
                }),
                'firmware_action': (self.run_shutdown_process,
                                    self.wait_yuck_screen_and_press_power,
                                    None,
                                    self.wait_fw_screen_and_ctrl_d),
            },
            {   # Step 4, enable normal mode and normal firmware.
                'state_checker': (self.crossystem_checker, {
                    'devsw_boot': '1',
                    'mainfw_type': 'developer',
                    'recoverysw_boot': '0',
                }),
                'userspace_action': self.enable_normal_mode_and_fw,
                'reboot_action': None,
            },
            {   # Step 5, turn on the recovery boot. Since a USB stick was
                # inserted in step 3, a recovery remove screen is shown.
                # Press power button to make DUT shutdown.
                'state_checker': (self.crossystem_checker, {
                    'devsw_boot': '0',
                    'mainfw_type': 'normal',
                    'recoverysw_boot': '0',
                }),
                'userspace_action': self.faft_client.request_recovery_boot,
                'firmware_action': (self.run_shutdown_process,
                                    self.wait_fw_screen_and_press_power),
            },
            {   # Step 6, done.
                'state_checker': (self.crossystem_checker, {
                    'devsw_boot': '0',
                    'mainfw_type': 'normal',
                    'recoverysw_boot': '0',
                }),
            },
        ))
        self.run_faft_sequence()
