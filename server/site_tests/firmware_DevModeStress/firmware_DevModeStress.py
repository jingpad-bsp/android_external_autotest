# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from threading import Timer
import logging
import time

from autotest_lib.client.common_lib import utils
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


def delayed(seconds):
    def decorator(f):
        def wrapper(*args, **kargs):
            t = Timer(seconds, f, args, kargs)
            t.start()
        return wrapper
    return decorator


class firmware_DevModeStress(FirmwareTest):
    """
    Servo based, iterative developer firmware boot test. One iteration
    of this test performs 2 reboots and 3 checks.
    """
    version = 1

    # Delay for waiting client to return before EC suspend
    EC_SUSPEND_DELAY = 5

    # Delay between EC suspend and wake
    WAKE_DELAY = 5

    @delayed(WAKE_DELAY)
    def wake_by_power_button(self):
        """Delay by WAKE_DELAY seconds and then wake DUT with power button."""
        self.servo.power_normal_press()

    def suspend_as_reboot(self, wake_func):
        """
        Suspend DUT and also kill FAFT client so that this acts like a reboot.

        Args:
          wake_func: A function that is called to wake DUT. Note that this
            function must delay itself so that we don't wake DUT before
            suspend_as_reboot returns.
        """
        cmd = '(sleep %d; powerd_dbus_suspend) &' % self.EC_SUSPEND_DELAY
        self.faft_client.system.run_shell_command(cmd)
        self.faft_client.disconnect()
        time.sleep(self.EC_SUSPEND_DELAY)
        wake_func()

    def initialize(self, host, cmdline_args):
        # Parse arguments from command line
        dict_args = utils.args_to_dict(cmdline_args)
        self.faft_iterations = int(dict_args.get('faft_iterations', 1))
        super(firmware_DevModeStress, self).initialize(host, cmdline_args)
        self.setup_dev_mode(dev_mode=True)
        self.setup_usbkey(usbkey=False)

    def run_once(self):
        for i in xrange(self.faft_iterations):
            logging.info('======== Running FAFT ITERATION %d/%s ========',
                         i + 1, self.faft_iterations)
            logging.info("Verify dev mode.")
            self.check_state((self.checkers.crossystem_checker, {
                                'devsw_boot': '1',
                                'mainfw_type': 'developer',
                                }))
            self.reboot_warm(wait_for_dut_up=False)
            self.wait_dev_screen_and_ctrl_d()
            self.wait_for_client()

            logging.info("Verify dev mode after soft reboot.")
            self.check_state((self.checkers.crossystem_checker, {
                                'devsw_boot': '1',
                                'mainfw_type': 'developer',
                                }))
            self.do_reboot_action((self.suspend_as_reboot,
                                   self.wake_by_power_button))
            self.wait_for_client()

        logging.info("Complete, final check for dev mode.")
        self.check_state((self.checkers.crossystem_checker, {
                            'devsw_boot': '1',
                            'mainfw_type': 'developer',
                            }))
