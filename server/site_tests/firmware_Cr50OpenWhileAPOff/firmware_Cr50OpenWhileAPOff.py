# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft.cr50_test import Cr50Test


class firmware_Cr50OpenWhileAPOff(Cr50Test):
    """Verify the console can be opened while the AP is off.

    Make sure it runs ok when cr50 saw the AP turn off and when it resets while
    the AP is off.

    This test would work the same with any cr50 ccd command that uses vendor
    commands. 'ccd open' is just one.
    """
    version = 1

    SLEEP_DELAY = 20
    SHORT_DELAY = 2

    def initialize(self, host, cmdline_args, ccd_lockout):
        """Initialize the test"""
        self.changed_dut_state = False
        super(firmware_Cr50OpenWhileAPOff, self).initialize(host, cmdline_args)

        if not hasattr(self, 'cr50'):
            raise error.TestNAError('Test can only be run on devices with '
                                    'access to the Cr50 console')

        # TODO(mruthven): replace with dependency on servo v4 with servo micro
        # and type c cable.
        if 'servo_v4_with_servo_micro' != self.servo.get_servo_version():
            raise error.TestNAError('Run using servo v4 with servo micro')

        self.ccd_lockout = ccd_lockout

        if not self.cr50.has_command('ccdstate'):
            raise error.TestNAError('Cannot test on Cr50 with old CCD version')

        dts_mode_works = self.cr50.servo_v4_supports_dts_mode()
        if not dts_mode_works:
            raise error.TestNAError('Plug in servo v4 type c cable into ccd '
                    'port')

        self.changed_dut_state = True
        self.hold_ec_in_reset = True
        if not self.reset_device_get_deep_sleep_count(True):
            # Some devices can't tell the AP is off when the EC is off. Try
            # deep sleep with just the AP off.
            self.hold_ec_in_reset = False
            # If deep sleep doesn't work at all, we can't run the test.
            if not self.reset_device_get_deep_sleep_count(True):
                raise error.TestNAError('Skipping test on device without deep '
                        'sleep support')
            # We can't hold the ec in reset and enter deep sleep. Switch to
            # using the function that will just verify the console doesn't hang
            # instead of doing full open. The power button required for full
            # open would wake up the AP.
            self.ccd_func = self.send_ccd_cmd
            logging.info("deep sleep doesn't work with EC in reset. Testing "
                    "basic ccd open")
        elif self.ccd_lockout:
            # If ccd is locked out just send the ccd command and make sure you
            # get a response. You don't care if ccd open succeeds
            self.ccd_func = self.send_ccd_cmd
            logging.info('CCD is locked out. Testing basic ccd open')
        else:
            # With ccd accessible and deep sleep working while the EC is reset,
            # the test can fully verify ccd open.
            self.ccd_func = self.cr50.set_ccd_level
            logging.info('Deep sleep works with the EC in reset. Testing full '
                    'ccd open')


    def cleanup(self):
        """Make sure the device is on at the end of the test"""
        # If we got far enough to start changing the DUT power state, attempt to
        # turn the DUT back on and reenable the cr50 console.
        if self.changed_dut_state:
            self.restore_dut()
        super(firmware_Cr50OpenWhileAPOff, self).cleanup()


    def restore_dut(self):
        """Turn on the device and reset cr50

        Do a deep sleep reset to fix the cr50 console. Then turn the device on.

        Raises:
            TestFail if the cr50 console doesn't work
        """
        logging.info('attempt cr50 console recovery')

        # The console may be hung. Run through reset manually, so we dont need
        # the console.
        self.turn_device('off')
        # Toggle dts mode to enter and exit deep sleep
        self.toggle_dts_mode()
        # Turn the device back on
        self.turn_device('on')

        # Verify the cr50 console responds to commands.
        try:
            logging.info(self.cr50.send_command_get_output('ccdstate',
                    ['ccdstate.*>']))
        except error.TestFail, e:
            if 'Timeout waiting for response' in e.message:
                raise error.TestFail('Could not restore Cr50 console')
            raise


    def turn_device(self, state):
        """Turn the device off or on.

        If we are testing ccd open fully, it will also assert EC reset so power
        button presses wont turn on the AP
        """
        # Make sure to release the EC from reset before trying anything
        self.servo.set('cold_reset', 'off')

        time.sleep(self.SHORT_DELAY)

        # Turn off the AP
        if state == 'off':
            self.servo.set_nocheck('power_state', 'off')
            time.sleep(self.SHORT_DELAY)

        # Hold the EC in reset or release it from reset based on state
        if self.hold_ec_in_reset:
            # cold reset is the inverse of device state, so convert the state
            self.servo.set('cold_reset', 'on' if state == 'off' else 'off')
            time.sleep(self.SHORT_DELAY)

        # Turn on the AP
        if state == 'on':
            self.servo.power_short_press()


    def reset_device_get_deep_sleep_count(self, deep_sleep):
        """Reset the device. Use dts mode to enable deep sleep if requested.

        Args:
            deep_sleep: True if Cr50 should enter deep sleep

        Returns:
            The number of times Cr50 entered deep sleep during reset
        """
        self.turn_device('off')
        # Do a deep sleep reset to restore the cr50 console.
        ds_count = self.deep_sleep_reset_get_count() if deep_sleep else 0
        self.turn_device('on')
        return ds_count


    def toggle_dts_mode(self):
        """Toggle DTS mode to enable and disable deep sleep"""
        # We cant use cr50 ccd_disable/enable, because those uses the cr50
        # console. Call servo_v4_dts_mode directly.
        self.servo.set_nocheck('servo_v4_dts_mode', 'off')
        time.sleep(self.SLEEP_DELAY)
        self.servo.set_nocheck('servo_v4_dts_mode', 'on')


    def deep_sleep_reset_get_count(self):
        """Toggle ccd to get to do a deep sleep reset

        Returns:
            The number of times cr50 entered deep sleep
        """
        start_count = self.cr50.get_deep_sleep_count()
        # CCD is what's keeping Cr50 awake. Toggle DTS mode to turn off ccd
        # so cr50 will enter deep sleep
        self.toggle_dts_mode()
        # Return the number of times cr50 entered deep sleep.
        return self.cr50.get_deep_sleep_count() - start_count


    def send_ccd_cmd(self, state):
        """Send the cr50 command ccd command. Make sure access is denied"""
        logging.info('running lockout check %s', state)
        rv = self.cr50.send_command_get_output('ccd %s' % state , ['ccd.*>'])[0]
        logging.info(rv)
        if self.ccd_lockout != ('Access Denied' in rv):
            raise error.TestFail('CCD is not %s' % ('locked out' if
                    self.ccd_lockout else 'available'))


    def try_ccd_open(self, cr50_reset):
        """Try 'ccd open' and make sure the console doesn't hang"""
        self.ccd_func('lock')
        try:
            self.turn_device('off')
            if cr50_reset:
                if not self.deep_sleep_reset_get_count():
                    raise error.TestFail('Did not detect a cr50 reset')
            # Verify ccd open
            self.ccd_func('open')
        finally:
            self.restore_dut()


    def run_once(self):
        """Turn off the AP and try ccd open."""
        self.try_ccd_open(False)
        self.try_ccd_open(True)
