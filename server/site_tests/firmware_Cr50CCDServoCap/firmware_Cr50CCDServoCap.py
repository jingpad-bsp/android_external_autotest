# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import pprint
import re
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft.cr50_test import Cr50Test


class firmware_Cr50CCDServoCap(Cr50Test):
    """Verify Cr50 CCD output enable/disable when servo is connected.

    Verify Cr50 will enable/disable the CCD servo output capabilities when servo
    is attached/detached.
    """
    version = 1

    # Time used to wait for Cr50 to detect the servo state. Cr50 updates the ccd
    # state once a second. Wait 2 seconds to be conservative.
    SLEEP = 2

    # The responses we care about for ccdstate
    #
    # We look for the exact states, so send_command_get_output can tell if we
    # are missing any of the output and retry.
    #
    # TODO(b/80540170): change ccdstate regex to 'ccdstate.*>' when we know the
    # cr50 console wont drop characters
    CCDSTATE_RESPONSE_LIST = [
        'ccdstate',
        'Rdd:\s+(disconnected|connected|undetectable)',
        'Servo:\s+(disconnected|connected|undetectable)',
        'State flags:\s+(UARTAP(\+TX)? )?UARTEC(\+TX)?( I2C)?( SPI)?[\r\n]',
        '>'
    ]
    # A list of the actions we should verify
    TEST_CASES = [
        'fake_servo on, cr50_run reboot',
        'fake_servo on, rdd attach, cr50_run reboot',

        'rdd attach, fake_servo on, cr50_run reboot, fake_servo off',
        'rdd attach, fake_servo on, rdd detach',
        'rdd attach, fake_servo off, rdd detach',
    ]
    ON = 'on'
    OFF = 'off'
    UNDETECTABLE = 'undetectable'
    DETECTABLE = 'detectable'
    # There are many valid CCD state strings. These lists define which strings
    # translate to off, on and unknown.
    #
    # The 'State flags' values are modified to ignore I2C. Hardware may or may
    # not have the INAs populated. The I2C pin is open drain, so if the hardware
    # isn't setup we can't tell what cr50 is even trying to do with the signal.
    # This test completely ignores the I2C flags, because it is not useful.
    STATE_VALUES = {
        OFF : ['off', 'disconnected', 'disabled', 'UARTAP UARTEC', 'UARTEC'],
        ON : ['on', 'connected', 'enabled'],
        UNDETECTABLE : ['undetectable'],
        DETECTABLE : ['disconnected', 'connected'],
    }
    # When CCD is locked out the 'on' state flags will look like this
    ON_CCD_LOCKOUT = ['UARTAP+TX UARTEC']
    # When CCD is accessible the 'on' state flags will look like this
    ON_CCD_ACCESSIBLE = ['UARTAP+TX UARTEC+TX SPI', 'UARTEC+TX SPI']
    # RESULT_ORDER is a list of the CCD state strings. The order corresponds
    # with the order of the key states in EXPECTED_RESULTS.
    RESULT_ORDER = ['State flags', 'CCD EXT', 'Servo']
    # A dictionary containing an order of steps to verify and the expected ccd
    # states as the value.
    #
    # The keys are a list of strings with the order of steps to run.
    #
    # The values are the expected state of [state flags, ccd ext, servo]. The
    # ccdstate strings are in RESULT_ORDER. The order of the EXPECTED_RESULTS
    # key states must match the order in RESULT_ORDER.
    #
    # There are three valid states: UNDETECTABLE, ON, or OFF. Undetectable only
    # describes the servo state when EC uart is enabled. If the ec uart is
    # enabled, cr50 cannot detect servo and the state becomes undetectable. All
    # other ccdstates can only be off or on. Cr50 has a lot of different words
    # for off and on. These other descriptors are in STATE_VALUES.
    EXPECTED_RESULTS = {
        # The state all tests will start with. Servo and the ccd cable are
        # disconnected.
        'reset_ccd state' : [OFF, OFF, OFF],

        # If rdd is attached all ccd functionality will be enabled, and servo
        # will be undetectable.
        'rdd attach' : [ON, ON, UNDETECTABLE],

        # Cr50 cannot detect servo if ccd has been enabled first
        'rdd attach, fake_servo off' : [ON, ON, UNDETECTABLE],
        'rdd attach, fake_servo off, rdd detach' : [OFF, OFF, OFF],
        'rdd attach, fake_servo on' : [ON, ON, UNDETECTABLE],
        'rdd attach, fake_servo on, rdd detach' : [OFF, OFF, ON],
        # Cr50 can detect servo after a reboot even if rdd was attached before
        # servo.
        'rdd attach, fake_servo on, cr50_run reboot' : [OFF, ON, ON],
        # Once servo is detached, Cr50 will immediately reenable the EC uart.
        'rdd attach, fake_servo on, cr50_run reboot, fake_servo off' :
            [ON, ON, UNDETECTABLE],

        # Cr50 can detect a servo attach
        'fake_servo on' : [OFF, OFF, ON],
        # Cr50 knows servo is attached when ccd is enabled, so it wont enable
        # uart.
        'fake_servo on, rdd attach' : [OFF, ON, ON],
        'fake_servo on, rdd attach, cr50_run reboot' : [OFF, ON, ON],
        'fake_servo on, cr50_run reboot' : [OFF, OFF, ON],
    }

    # Results that will be slightly different if ccd is locked out.
    EXPECTED_CCD_LOCKOUT_RESULTS = {
        # When CCD is disabled we can always detect servo.
        'rdd attach' : [ON, ON, DETECTABLE],

        # Cr50 can always detect servo if ccd is locked out
        'rdd attach, fake_servo off' : [ON, ON, OFF],
        'rdd attach, fake_servo on' : [OFF, ON, ON],
    }


    def initialize(self, host, cmdline_args, full_args):
        super(firmware_Cr50CCDServoCap, self).initialize(host, cmdline_args,
                full_args)
        if not hasattr(self, 'cr50'):
            raise error.TestNAError('Test can only be run on devices with '
                                    'access to the Cr50 console')

        if self.servo.get_servo_version() != 'servo_v4_with_servo_micro':
            raise error.TestNAError('Must use servo v4 with servo micro')

        if not self.cr50.has_command('ccdstate'):
            raise error.TestNAError('Cannot test on Cr50 with old CCD version')

        if not self.cr50.servo_v4_supports_dts_mode():
            raise error.TestNAError('Need working servo v4 DTS control')

        if self.ccd_lockout:
            self.STATE_VALUES[self.ON].extend(self.ON_CCD_LOCKOUT)
            logging.info('ccd is locked out. Skipping ccd initialization')
            return
        else:
            self.STATE_VALUES[self.ON].extend(self.ON_CCD_ACCESSIBLE)

        self.check_servo_monitor()
        # Make sure cr50 is open with testlab enabled.
        self.fast_open(enable_testlab=True)
        if not self.cr50.testlab_is_on():
            raise error.TestNAError('Cr50 testlab mode needs to be enabled')
        logging.info('Cr50 is %s', self.servo.get('cr50_ccd_level'))
        self.cr50.set_cap('UartGscTxECRx', 'Always')


    def cleanup(self):
        """Reenable the EC uart"""
        self.fake_servo('on')
        self.rdd('detach')
        self.rdd('attach')
        super(firmware_Cr50CCDServoCap, self).cleanup()


    def check_servo_monitor(self):
        """Make sure cr50 can detect servo connect and disconnect"""
        # Detach ccd so EC uart won't interfere with servo detection
        self.rdd('detach')
        servo_detect_error = error.TestNAError("Cannot run on device that does "
                "not support servo dectection with ec_uart_en:off/on")
        self.fake_servo('off')
        if self.get_ccdstate()['Servo'] not in self.STATE_VALUES[self.OFF]:
            raise servo_detect_error
        self.fake_servo('on')
        if self.get_ccdstate()['Servo'] not in self.STATE_VALUES[self.ON]:
            raise servo_detect_error


    def get_ccdstate(self):
        """Get the current Cr50 CCD states"""
        regex = '.*'.join(self.CCDSTATE_RESPONSE_LIST)
        rv = self.cr50.send_command_retry_get_output('ccdstate', [regex])[0][0]
        logging.info(rv)
        # I2C isn't a reliable flag, because the hardware often doesn't support
        # it. Remove any I2C flags from the ccdstate output.
        rv = rv.replace(' I2C', '')
        # Extract only the ccdstate output from rv
        ccdstates = re.findall('[ A-Za-z]+:[ A-Za-z\+_]+\r', rv)
        ccdstate = {}
        for line in ccdstates:
            line = line.strip()
            if line:
                k, v = line.split(':', 1)
                ccdstate[k.strip()] = v.strip()
        logging.info('Current CCD state:\n%s', pprint.pformat(ccdstate))
        return ccdstate


    def verify_ccdstate(self, run):
        """Verify the current state matches the expected result from the run.

        Args:
            run: the string representing the actions that have been run.

        Raises:
            TestError if any of the states are not correct
        """
        if run not in self.EXPECTED_RESULTS:
            raise error.TestError('Add results for %s to EXPECTED_RESULTS', run)
        expected_states = self.EXPECTED_RESULTS[run]

        # If ccd is locked out change the expected state
        if self.ccd_lockout and run in self.EXPECTED_CCD_LOCKOUT_RESULTS:
            expected_states = self.EXPECTED_CCD_LOCKOUT_RESULTS[run]

        # Wait a short time for the ccd state to settle
        time.sleep(self.SLEEP)

        mismatch = []
        ccdstate = self.get_ccdstate()
        for i, expected_state in enumerate(expected_states):
            name = self.RESULT_ORDER[i]
            if not expected_state:
                logging.info('No expected %s state skipping check', name)
                continue
            actual_state = ccdstate[name]
            valid_values = self.STATE_VALUES[expected_state]
            # Check that the current state is one of the valid states.
            if actual_state not in valid_values:
                mismatch.append('%s: "%s" not in "%s"' % (name, actual_state,
                    ', '.join(valid_values)))
        if mismatch:
            raise error.TestFail('Unexpected states after %s: %s' % (run,
                mismatch))


    def cr50_run(self, action):
        """Reboot cr50

        @param action: string 'reboot'
        """
        if action == 'reboot':
            self.cr50.reboot()
            self.cr50.send_command('ccd testlab open')
            time.sleep(self.SLEEP)


    def reset_ccd(self, state=None):
        """detach the ccd cable and disconnect servo.

        State is ignored. It just exists to be consistent with the other action
        functions.

        @param state: a var that is ignored
        """
        self.rdd('detach')
        self.fake_servo('off')


    def rdd(self, state):
        """Attach or detach the ccd cable.

        @param state: string 'attach' or 'detach'
        """
        self.servo.set_nocheck('servo_v4_dts_mode',
            'on' if state == 'attach' else 'off')
        time.sleep(self.SLEEP)


    def fake_servo(self, state):
        """Mimic servo on/off

        Cr50 monitors the servo EC uart tx signal to detect servo. If the signal
        is pulled up, then Cr50 will think servo is connnected. Enable the ec
        uart to enable the pullup. Disable the it to remove the pullup.

        It takes some time for Cr50 to detect the servo state so wait 2 seconds
        before returning.
        """
        self.servo.set('ec_uart_en', state)

        # Cr50 needs time to detect the servo state
        time.sleep(self.SLEEP)


    def run_steps(self, steps):
        """Do each step in steps and then verify the uart state.

        The uart state is order dependent, so we need to know all of the
        previous steps to verify the state. This will do all of the steps in
        the string and verify the Cr50 CCD uart state after each step.

        @param steps: a comma separated string with the steps to run
        """
        # The order of steps is separated by ', '. Remove the last step and
        # run all of the steps before it.
        separated_steps = steps.rsplit(', ', 1)
        if len(separated_steps) > 1:
            self.run_steps(separated_steps[0])

        step = separated_steps[-1]
        # The func and state are separated by ' '
        func, state = step.split(' ')
        logging.info('running %s', step)
        getattr(self, func)(state)

        # Verify the ccd state is correct
        self.verify_ccdstate(steps)


    def run_once(self):
        """Run through TEST_CASES and verify that Cr50 enables/disables uart"""
        for steps in self.TEST_CASES:
            # We dont have access to the reboot command when cr50 is locked out.
            # Skip any tests that rely on that.
            if self.ccd_lockout and 'cr50_run reboot' in steps:
                logging.info('SKIPPING: %s', steps)
                continue
            self.run_steps('reset_ccd state')
            logging.info('TESTING: %s', steps)
            self.run_steps(steps)
            logging.info('VERIFIED: %s', steps)
        if self.ccd_lockout:
            raise error.TestNAError('Cannot fully verify device state while '
                    'ccd is locked out')
