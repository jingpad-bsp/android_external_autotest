# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from itertools import groupby
import logging
from threading import Timer

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.server.cros.faftsequence import FAFTSequence

class firmware_FAFTSetup(FAFTSequence):
    """This test checks the following FAFT hardware requirement:
      - Warm reset
      - Cold reset
      - Recovery boot with USB stick
      - USB stick is plugged into Servo board, not DUT
      - Keyboard simulation
      - No terminal opened on EC console

    If this test is run with parameter -a "spec_check=True", then hardware
    testability is checked according to spec and without any current
    workaround. This includes:
      - Strict keyboard simulation
      - Recovery mode with dedicated recovery signal
    """
    version = 1


    def initialize(self, host, cmdline_args, use_pyauto=False, use_faft=True):
        dict_args = utils.args_to_dict(cmdline_args)
        spec_check = dict_args.get("spec_check", "False")
        if spec_check.lower() == "true":
            self._spec_check = True
        elif spec_check.lower() == "false":
            self._spec_check = False
        else:
            raise error.TestFail("Invalid argument spec_check=%s." % spec_check)
        super(firmware_FAFTSetup, self).initialize(host, cmdline_args,
                                                   use_pyauto, use_faft)

    def console_checker(self):
        """Verify EC console is available if using Chrome EC."""
        if not self.check_ec_capability(suppress_warning=True):
            # Not Chrome EC. Nothing to check.
            return True
        try:
            expected_output = ["Chip:\s+[^\r\n]*\r\n",
                               "RO:\s+[^\r\n]*\r\n",
                               "RW:\s+[^\r\n]*\r\n",
                               "Build:\s+[^\r\n]*\r\n"]
            self.ec.send_command_get_output("version",
                                            expected_output,
                                            timeout=0.2)
            return True
        except:
            logging.error("Cannot talk to EC console.")
            logging.error(
                    "Please check there is no terminal opened on EC console.")
            return False

    def base_keyboard_checker(self, press_action, expected_output):
        """Press key and check from DUT.

        Args:
            press_action: A callable that would press the keys when called.
            expected_output: Expected output from "showkey".
        """
        if not self.client_attr.has_keyboard:
            # Check all customized key commands are provided
            if not all([self._customized_ctrl_d_key_command,
                        self._customized_enter_key_command]):
                logging.error("No customized key command assigned.")
                return False

        # Stop UI so that key presses don't go to X.
        self.faft_client.run_shell_command("stop ui")
        # Press the keys
        press_action()
        lines = self.faft_client.run_shell_command_get_output("showkey")
        # Turn UI back on
        self.faft_client.run_shell_command("start ui")

        # We may be getting multiple key-press or key-release.
        # Let's remove duplicated items.
        dup_removed = [x[0] for x in groupby(lines)]
        dup_removed = dup_removed[-len(expected_output):]

        if dup_removed != expected_output:
            logging.error("Keyboard simulation not working correctly")
            logging.error("Captured keycodes:\n" + "\n".join(dup_removed))
            logging.error("Expected keycodes:\n" + "\n".join(expected_output))
            return False
        return True

    def keyboard_checker(self):
        """Press 'd', Ctrl, ENTER by servo and check from DUT."""
        def keypress():
            Timer(2, self.send_ctrl_d_to_dut).start()
            Timer(4, self.send_enter_to_dut).start()

        expected_output = [
                "keycode  29 press",
                "keycode  32 press",
                "keycode  32 release",
                "keycode  29 release",
                "keycode  28 press",
                "keycode  28 release"]

        return self.base_keyboard_checker(keypress, expected_output)

    def strict_keyboard_checker(self):
        """Press 'd', Ctrl, ENTER, Refresh by servo and check from DUT.

        This method directly controls keyboard by servo and thus cannot be used
        to test devices without internal keyboard.
        """
        def keypress():
            Timer(2, self.servo.ctrl_key).start()
            Timer(3, self.servo.d_key).start()
            Timer(4, self.servo.enter_key).start()
            Timer(5, self.servo.refresh_key).start()

        expected_output = [
                "keycode  29 press",
                "keycode  29 release",
                "keycode  32 press",
                "keycode  32 release",
                "keycode  28 press",
                "keycode  28 release",
                "keycode  61 press",
                "keycode  61 release"]

        return self.base_keyboard_checker(keypress, expected_output)

    def reboot_to_rec_mode(self):
        if self._spec_check:
            self.servo.enable_recovery_mode()
            self.servo.cold_reset()
            self.servo.disable_recovery_mode()
        else:
            self.enable_rec_mode_and_reboot()

    def run_once(self, host=None):
        self.register_faft_sequence((
            {   # Step 1, Check EC console is available and test warm reboot
                "state_checker": self.console_checker,
                "reboot_action": self.sync_and_warm_reboot,
            },
            {   # Step 2, Check test image in USB stick and recovery boot
                "userspace_action": self.assert_test_image_in_usb_disk,
                "reboot_action": self.reboot_to_rec_mode,
                "firmware_action": self.wait_fw_screen_and_plug_usb,
                "install_deps_after_boot": True,
            },
            {   # Step 3, Test cold reboot
                "state_checker": (self.crossystem_checker,
                                  {'mainfw_type': 'recovery'}),
                "reboot_action": self.sync_and_cold_reboot,
            },
            {   # Step 4, Check keyboard simulation
                "state_checker": (self.strict_keyboard_checker if
                                  self._spec_check and
                                  self.client_attr.has_keyboard else
                                  self.keyboard_checker),
            },
        ))
        self.run_faft_sequence()
