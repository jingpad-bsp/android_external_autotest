# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from itertools import groupby
import logging
from threading import Timer

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.server.cros.faft.faft_classes import FAFTSequence

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

    # Delay between starting 'showkey' and pressing the keys
    KEY_PRESS_DELAY = 2


    def initialize(self, host, cmdline_args):
        dict_args = utils.args_to_dict(cmdline_args)
        spec_check = dict_args.get("spec_check", "False")
        if spec_check.lower() == "true":
            self._spec_check = True
        elif spec_check.lower() == "false":
            self._spec_check = False
        else:
            raise error.TestFail("Invalid argument spec_check=%s." % spec_check)
        super(firmware_FAFTSetup, self).initialize(host, cmdline_args)

    def console_checker(self):
        """Verify EC console is available if using Chrome EC."""
        if not self.check_ec_capability(suppress_warning=True):
            # Not Chrome EC. Nothing to check.
            return True
        try:
            self.ec.send_command("chan 0")
            expected_output = ["Chip:\s+[^\r\n]*\r\n",
                               "RO:\s+[^\r\n]*\r\n",
                               "RW:\s+[^\r\n]*\r\n",
                               "Build:\s+[^\r\n]*\r\n"]
            self.ec.send_command_get_output("version",
                                            expected_output)
            self.ec.send_command("chan 0xffffffff")
            return True
        except: # pylint: disable=W0702
            logging.error("Cannot talk to EC console.")
            logging.error(
                    "Please check there is no terminal opened on EC console.")
            return False

    def compare_key_sequence(self, actual_seq, expected_seq):
        """Comparator for key sequence captured by 'showkey'

        This method compares if the last part of actual_seq matches
        expected_seq. If two or more key presses in expected_seq are in a
        tuple, their order are not compared. For example:
          expected_seq = [a, (b, c)]
        matches
          actual_seq = [a, b, c] or actual_seq = [a, c, b]
        This can be used to compare combo keys such as ctrl-D.

        Args:
          actual_seq: The actual key sequence captured by 'showkey'.
          expected_seq: The expected key sequence.
        """
        # Actual key sequence must be at least as long as the expected
        # sequence.
        expected_length = 0
        for s in expected_seq:
            if isinstance(s, tuple):
                expected_length += len(s)
            else:
                expected_length += 1
        if len(actual_seq) < expected_length:
            return False

        # We only care about the last part of actual_seq. Let's reverse both
        # sequences so that we can easily compare them backward.
        actual_seq.reverse()
        expected_seq.reverse()
        index = 0
        for s in expected_seq:
            if isinstance(s, tuple):
                length = len(s)
                actual = actual_seq[index:index + length]
                actual.sort()
                expected = list(s)
                expected.sort()
                if actual != expected:
                    return False
                index += length
            else:
                if actual_seq[index] != s:
                    return False
                index += 1
        return True

    def key_sequence_string(self, key_seq):
        """Get a human readable key sequence string.

        Args:
          key_seq: A list contains strings and/or tuple of strings.
        """
        s = []
        for k in key_seq:
            if isinstance(k, tuple):
                s.append("---Unordered---")
                s.extend(k)
                s.append("---------------")
            else:
                s.append(k)
        return "\n".join(s)

    def base_keyboard_checker(self, press_action, expected_output):
        """Press key and check from DUT.

        Args:
            press_action: A callable that would press the keys when called.
            expected_output: Expected output from "showkey".
        """
        # Stop UI so that key presses don't go to X.
        self.faft_client.system.run_shell_command("stop ui")
        # Press the keys
        Timer(self.KEY_PRESS_DELAY, press_action).start()
        lines = self.faft_client.system.run_shell_command_get_output("showkey")
        # Turn UI back on
        self.faft_client.system.run_shell_command("start ui")

        # We may be getting multiple key-press or key-release.
        # Let's remove duplicated items.
        dup_removed = [x[0] for x in groupby(lines)]

        if not self.compare_key_sequence(dup_removed, expected_output):
            logging.error("Keyboard simulation not working correctly")
            logging.error("Captured keycodes:\n%s", "\n".join(dup_removed))
            logging.error("Expected keycodes:\n%s",
                          self.key_sequence_string(expected_output))
            return False
        return True

    def keyboard_checker(self):
        """Press 'd', Ctrl, ENTER by servo and check from DUT."""
        def keypress():
            self.press_ctrl_d()
            self.press_enter()

        keys = self.faft_config.key_checker

        expected_output = [
                ("keycode  {0:x} {1}".format(keys[0][0], keys[0][1]),
                 "keycode  {0:x} {1}".format(keys[1][0], keys[1][1])),
                ("keycode  {0:x} {1}".format(keys[2][0], keys[2][1]),
                 "keycode  {0:x} {1}".format(keys[3][0], keys[3][1])),
                "keycode  {0:x} {1}".format(keys[4][0], keys[4][1]),
                "keycode  {0:x} {1}".format(keys[5][0], keys[5][1])]

        return self.base_keyboard_checker(keypress, expected_output)

    def strict_keyboard_checker(self):
        """Press 'd', Ctrl, ENTER, Refresh by servo and check from DUT.

        This method directly controls keyboard by servo and thus cannot be used
        to test devices without internal keyboard.
        """
        def keypress():
            self.servo.ctrl_key()
            self.servo.d_key()
            self.servo.enter_key()
            self.servo.refresh_key()

        keys = self.faft_config.key_checker_strict

        expected_output = list("keycode  %x %s" % (k, p) for k, p in keys)

        return self.base_keyboard_checker(keypress, expected_output)

    def reboot_to_rec_mode(self):
        if self._spec_check:
            self.servo.enable_recovery_mode()
            self.servo.get_power_state_controller().cold_reset()
            self.servo.disable_recovery_mode()
        else:
            self.enable_rec_mode_and_reboot()

    def run_once(self):
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
                "state_checker": (self.checkers.crossystem_checker,
                                  {'mainfw_type': 'recovery'}),
                "reboot_action": self.sync_and_cold_reboot,
            },
            {   # Step 4, Check keyboard simulation
                "state_checker": (self.strict_keyboard_checker if
                                  self._spec_check and
                                  self.faft_config.has_keyboard else
                                  self.keyboard_checker),
            },
        ))
        self.run_faft_sequence()
