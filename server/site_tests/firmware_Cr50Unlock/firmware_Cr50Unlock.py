# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest, test
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_Cr50Unlock(FirmwareTest):
    """Verify cr50 unlock.

    Enable the lock on cr50, run 'lock disable', and then press the power
    button until it is unlocked.
    """
    version = 1

    LOCK_ON = 'on'
    LOCK_OFF = 'off'
    START_UNLOCK_TIMEOUT = 20
    UNLOCK = ['Unlock sequence starting. Continue until (\S+)']
    GETTIME = ['= (\S+)']
    ACCESS_DENIED = 'Access Denied'


    def initialize(self, host, cmdline_args):
        super(firmware_Cr50Unlock, self).initialize(host, cmdline_args)
        if not hasattr(self, 'cr50'):
            raise error.TestNAError('Test can only be run on devices with '
                                    'access to the Cr50 console')
        if self.cr50.using_ccd():
            raise error.TestNAError('Use a flex cable instead of CCD cable.')

        # The unlock process takes a while to start. Increase the cr50 console
        # timeout so we can get the entire output of the 'lock disable' start
        # process
        self.original_timeout = self.servo.get('cr50_console_timeout')
        self.servo.set_nocheck('cr50_console_timeout',
                               self.START_UNLOCK_TIMEOUT)


    def cleanup(self):
        """Restore the original cr50 console timeout"""
        self.servo.set_nocheck('cr50_console_timeout', self.original_timeout)
        super(firmware_Cr50Unlock, self).cleanup()


    def get_lock(self):
        """Return the state of ccd_lock"""
        return self.servo.get('ccd_lock')


    def press_pwrbtn_and_get_lock(self):
        """Press the power button then return the lock state"""
        self.servo.power_short_press()
        return self.get_lock()


    def run_once(self):
        # Enable the lock
        rv = self.cr50.send_command_get_output('lock enable', ['[\w\s]+'])
        # Certain prod images are permanently locked out. We can't do anything
        # on these images.
        if self.ACCESS_DENIED in rv[0]:
            raise error.TestNAError('Cr50 image is permanently locked.')

        lock_state = utils.wait_for_value(self.get_lock, self.LOCK_ON)
        if lock_state != self.LOCK_ON:
            raise error.TestError('Could not enable lock')

        # Get the current time.
        rv = self.cr50.send_command_get_output('gettime', self.GETTIME)
        current_time = float(rv[0][1])

        # Start the unlock process.
        rv = self.cr50.send_command_get_output('lock disable', self.UNLOCK)
        unlock_finished = float(rv[0][1])

        # Calculate the unlock timeout. There is a 10s countdown to start the
        # unlock process, so unlock_timeout will be around 10s longer than
        # necessary.
        unlock_timeout = int(unlock_finished - current_time)
        logging.info('Pressing power button up to %ds to perform unlock',
                     unlock_timeout)

        # Press the power button until the lock is disabled.
        lock_state = utils.wait_for_value(self.press_pwrbtn_and_get_lock,
                                          self.LOCK_OFF,
                                          timeout_sec=unlock_timeout)
        if lock_state != self.LOCK_OFF:
            raise error.TestError('Could not disable lock')

        logging.info('Successfully disabled the lock')
