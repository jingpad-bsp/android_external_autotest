# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time


class ModeSwitcher(object):
    """Class that controls firmware mode switching."""

    def __init__(self, faft_framework):
        self.faft_framework = faft_framework
        self.faft_client = faft_framework.faft_client
        self.servo = faft_framework.servo
        self.faft_config = faft_framework.faft_config
        self.checkers = faft_framework.checkers
        self._backup_mode = None


    def setup_mode(self, mode):
        """Setup for the requested mode.

        It makes sure the system in the requested mode. If not, it tries to
        do so.

        @param mode: A string of mode, one of 'normal', 'dev', or 'rec'.
        """
        if not self.checkers.mode_checker(mode):
            logging.info('System not in expected %s mode. Reboot into it.',
                         mode)
            if self._backup_mode is None:
                # Only resume to normal/dev mode after test, not recovery.
                self._backup_mode = 'dev' if mode == 'normal' else 'normal'
            self.reboot_to_mode(mode)


    def restore_mode(self):
        """Restores original dev mode status if it has changed."""
        if self._backup_mode is not None:
            self.reboot_to_mode(self._backup_mode)


    def reboot_to_mode(self, to_mode, from_mode=None, wait_for_dut_up=True):
        """Reboot and execute the mode switching sequence.

        @param to_mode: The target mode, one of 'normal', 'dev', or 'rec'.
        @param from_mode: The original mode, optional, one of 'normal, 'dev',
                          or 'rec'.
        @param wait_for_dut_up: True to wait DUT online again. False to do the
                                reboot and mode switching sequence only and may
                                need more operations to pass the firmware
                                screen.
        """
        logging.info('-[ModeSwitcher]-[ start reboot_to_mode(%r, %r, %r) ]-',
                     to_mode, from_mode, wait_for_dut_up)
        if to_mode == 'rec':
            self._enable_rec_mode_and_reboot(usb_state='dut')
            if wait_for_dut_up:
                # In the keyboard controlled recovery mode design, it doesn't
                # require users to remove and insert the USB.
                #
                # In the old design, it checks:
                #   if dev_mode ON, directly boot to USB stick if presented;
                #   if dev_mode OFF,
                #     the old models need users to remove and insert the USB;
                #     the new models directly boot to the USB.
                if not self.faft_config.keyboard_dev and from_mode == 'normal':
                    self.faft_framework.wait_fw_screen_and_plug_usb()
                self.faft_framework.wait_for_client(install_deps=True)

        elif to_mode == 'dev':
            self._enable_dev_mode_and_reboot()
            if wait_for_dut_up:
                self.faft_framework.wait_dev_screen_and_ctrl_d()
                self.faft_framework.wait_for_client()

        elif to_mode == 'normal':
            self._enable_normal_mode_and_reboot()
            if wait_for_dut_up:
                self.faft_framework.wait_for_client()

        else:
            raise NotImplementedError(
                    'Not supported mode switching from %s to %s' %
                     (str(from_mode), to_mode))
        logging.info('-[ModeSwitcher]-[ end reboot_to_mode(%r, %r, %r) ]-',
                     to_mode, from_mode, wait_for_dut_up)


    def _enable_rec_mode_and_reboot(self, usb_state=None):
        """Switch to rec mode and reboot.

        This method emulates the behavior of the old physical recovery switch,
        i.e. switch ON + reboot + switch OFF, and the new keyboard controlled
        recovery mode, i.e. just press Power + Esc + Refresh.

        @param usb_state: A string, one of 'dut', 'host', or 'off'.
        """
        self.faft_framework.blocking_sync()
        psc = self.servo.get_power_state_controller()
        psc.power_off()
        if usb_state:
            self.servo.switch_usbkey(usb_state)
        psc.power_on(psc.REC_ON)


    def _enable_dev_mode_and_reboot(self):
        """Switch to developer mode and reboot."""
        if self.faft_config.keyboard_dev:
            self._enable_keyboard_dev_mode()
        else:
            self.servo.enable_development_mode()
            self.faft_client.system.run_shell_command(
                    'chromeos-firmwareupdate --mode todev && reboot')


    def _enable_normal_mode_and_reboot(self):
        """Switch to normal mode and reboot."""
        if self.faft_config.keyboard_dev:
            self._disable_keyboard_dev_mode()
        else:
            self.servo.disable_development_mode()
            self.faft_client.system.run_shell_command(
                    'chromeos-firmwareupdate --mode tonormal && reboot')


    def _enable_keyboard_dev_mode(self):
        """Enable keyboard controlled developer mode"""
        logging.info("Enabling keyboard controlled developer mode")
        # Rebooting EC with rec mode on. Should power on AP.
        # Plug out USB disk for preventing recovery boot without warning
        self._enable_rec_mode_and_reboot(usb_state='host')
        self.faft_framework.wait_for_client_offline()
        self._wait_fw_screen_and_switch_keyboard_dev_mode(dev=True)

        # TODO (crosbug.com/p/16231) remove this conditional completely if/when
        # issue is resolved.
        if self.faft_config.platform == 'Parrot':
            self.faft_framework.wait_for_client_offline()
            self.faft_framwork.reboot_cold_trigger()


    def _disable_keyboard_dev_mode(self):
        """Disable keyboard controlled developer mode"""
        logging.info("Disabling keyboard controlled developer mode")
        if (not self.faft_config.chrome_ec and
            not self.faft_config.broken_rec_mode):
            self.servo.disable_recovery_mode()
        self.faft_framework.sync_and_cold_reboot()
        self.faft_framework.wait_for_client_offline()
        self._wait_fw_screen_and_switch_keyboard_dev_mode(dev=False)


    def _wait_fw_screen_and_switch_keyboard_dev_mode(self, dev):
        """Wait for firmware screen and then switch into or out of dev mode.

        @param dev: True if switching into dev mode. Otherwise, False.
        """
        time.sleep(self.faft_config.firmware_screen)
        if dev:
            self.servo.ctrl_d()
            time.sleep(self.faft_config.confirm_screen)
            if self.faft_config.rec_button_dev_switch:
                logging.info('RECOVERY button pressed to switch to dev mode')
                self.servo.set('rec_mode', 'on')
                time.sleep(self.faft_config.hold_cold_reset)
                self.servo.set('rec_mode', 'off')
            else:
                logging.info('ENTER pressed to switch to dev mode')
                self.servo.enter_key()
        else:
            self.servo.enter_key()
            time.sleep(self.faft_config.confirm_screen)
            self.servo.enter_key()
