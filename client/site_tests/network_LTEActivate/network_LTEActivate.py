# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

import dbus
import dbus.types
import logging
import time

from autotest_lib.client.cros import backchannel
from autotest_lib.client.cros.cellular import mm
from autotest_lib.client.cros.cellular.pseudomodem import modem_3gpp
from autotest_lib.client.cros.cellular.pseudomodem import mm1, pseudomodem, sim

# pylint: disable=W0611
from autotest_lib.client.cros import flimflam_test_path
# pylint: enable=W0611
import cellular_proxy

I_ACTIVATION_TEST = 'Interface.LTEActivationTest'

LONG_TIMEOUT = 20
SHORT_TIMEOUT = 10

class ActivationTest(object):
    """
    Super class that implements setup code that is common to the individual
    tests.

    """
    class TestModem(modem_3gpp.Modem3gpp):
        """
        Base class for the custom 3GPP fake modems that are defined in this
        test.

        """
        def _InitializeProperties(self):
            props = modem_3gpp.Modem3gpp._InitializeProperties(self)
            modem_props = props[mm1.I_MODEM]
            modem_props['OwnNumbers'] = ['0000000000']
            modem_props['AccessTechnologies'] = dbus.types.UInt32(
                mm1.MM_MODEM_ACCESS_TECHNOLOGY_LTE)
            modem_props['ModemCapabilities'] = dbus.types.UInt32(
                mm1.MM_MODEM_CAPABILITY_LTE)
            modem_props['CurrentCapabilities'] = dbus.types.UInt32(
                mm1.MM_MODEM_CAPABILITY_LTE)

            # For the purposes of this test, introduce a property to help
            # verify that a reset has taken place. Expose this under a test
            # specific interface.
            if hasattr(self, '_properties'):
                reset_called = \
                    self._properties[I_ACTIVATION_TEST]['ResetCalled']
            else:
                reset_called = False
            props[I_ACTIVATION_TEST] = {
                'ResetCalled' : dbus.types.Boolean(reset_called)
            }
            return props

        def RegisterWithNetwork(
                self, operator_id='', return_cb=None, raise_cb=None):
            # Make this do nothing, so that we don't automatically
            # register to a network after enable.
            return

        def Reset(self):
            self.Set(
                I_ACTIVATION_TEST, 'ResetCalled', dbus.types.Boolean(True))
            modem_3gpp.Modem3gpp.Reset(self)

    def __init__(self, pmm_context, test):
        self.pmm_context = pmm_context
        self.test = test
        self.test_modem = self.SetupTestModem()

    def Cleanup(self):
        """
        Makes the modem look like it has been activated to satisfy the test
        end condition.

        """
        # Set the MDN to a non-zero value, so that shill removes the ICCID from
        # activating_iccid_store.profile. This way, individual test runs won't
        # interfere with each other.
        modem = self.test.GetModem()
        modem.PropertiesInterface().Set(mm1.I_MODEM,
                                        'OwnNumbers',
                                        ['1111111111'])
        time.sleep(5)
        if self.test.FindCellularService(False):
            self.test.CheckServiceActivationState('activated')

    def Run(self):
        """
        Configures the pseudomodem to run with the test modem, runs the test
        and cleans up.

        """
        if not self.test_modem:
            raise test.TestFail('Uninitialized test modem')
        self.pmm_context.SetModem(self.test_modem)
        time.sleep(5)
        self.RunTest()
        self.Cleanup()

    def SetupTestModem(self):
        """
        Returns the modem.Modem3gpp implementation that will be used by the
        test. Should be implemented by the subclass.

        @return An instance of ActivationTest.TestModem.

        """
        raise NotImplementedError()

    def RunTest(self):
        """
        Runs the body of the test. Should be implemented by the subclass.

        """
        raise NotImplementedError()

class TimeoutResetTest(ActivationTest):
    """
    This test verifies that the modem resets after a timeout following online
    payment.

    """
    def SetupTestModem(self):
        return ActivationTest.TestModem()

    def RunTest(self):
        # Service should appear as 'not-activated'.
        self.test.CheckServiceActivationState('not-activated')
        self.test.CheckResetCalled(False)

        # Call 'CompleteActivation' on the device. The service should become
        # 'activating' and the modem should reset after 20 seconds.
        service = self.test.FindCellularService()
        service.CompleteCellularActivation()
        self.test.CheckServiceActivationState('activating')

        # Wait until the register timeout.
        time.sleep(LONG_TIMEOUT)
        self.test.CheckResetCalled(True)

        # At this point, a service should never get created.
        if self.test.FindCellularService(False):
            raise error.TestError('There should be no cellular service.')

class TimeoutActivatedTest(ActivationTest):
    """
    This test verifies that the service eventually becomes 'activated' in the
    case of a post-payment registration timeout but the modem finally registers
    to a network after a reset.

    """
    def SetupTestModem(self):
        class Modem(ActivationTest.TestModem):
            """
            Fake modem that only becomes registered if it has been reset at
            least once.

            """
            def RegisterWithNetwork(
                    self, operator_id='', return_cb=None, raise_cb=None):
                if self.Get(I_ACTIVATION_TEST, 'ResetCalled'):
                    modem_3gpp.Modem3gpp.RegisterWithNetwork(
                            self, operator_id, return_cb, raise_cb)
        return Modem()

    def RunTest(self):
        # Service should appear as 'not-activated'.
        self.test.CheckServiceActivationState('not-activated')
        self.test.CheckResetCalled(False)

        # Call 'CompleteActivation' on the device. The service should become
        # 'activating' and the modem should reset after 20 seconds.
        service = self.test.FindCellularService()
        service.CompleteCellularActivation()
        self.test.CheckServiceActivationState('activating')

        # Wait until the register timeout.
        time.sleep(LONG_TIMEOUT)
        self.test.CheckResetCalled(True)

        # The service should register and be marked as 'activated'.
        self.test.CheckServiceActivationState('activated')

class ResetAfterRegisterTest(ActivationTest):
    """
    This test verifies that shill resets the modem if the modem registers
    with a network within the timeout interval.

    """
    def SetupTestModem(self):
        class Modem(ActivationTest.TestModem):
            """
            Fake modem that becomes registered once registration has been
            triggered at least twice.

            """
            def __init__(self):
                ActivationTest.TestModem.__init__(self)
                self.register_count = 0

            def RegisterWithNetwork(
                    self, operator_id='', return_cb=None, raise_cb=None):
                # Make the initial registration due triggered by Enable do
                # nothing. We expect exactly two Enable commands:
                #   1. Triggered by shill to enable the modem,
                #   2. Triggered by ResetCellularDevice in
                #      ResetAfterRegisterTest.RunTest.
                self.register_count += 1
                if self.register_count > 1:
                    modem_3gpp.Modem3gpp.RegisterWithNetwork(
                            self, operator_id, return_cb, raise_cb)
        return Modem()

    def RunTest(self):
        # Service should appear as 'not-activated'.
        self.test.CheckServiceActivationState('not-activated')

        # Call 'CompleteActivation' on the device. The service should become
        # 'activating' and the modem should reset after 20 seconds.
        service = self.test.FindCellularService()
        service.CompleteCellularActivation()
        self.test.CheckServiceActivationState('activating')

        time.sleep(5)
        self.test.CheckResetCalled(False)

        # The service should register and trigger shill to reset the modem.
        self.test.EnsureModemStateReached(
                mm1.MM_MODEM_STATE_ENABLED, SHORT_TIMEOUT)
        time.sleep(5)
        mccmnc = self.test.sim.Get(mm1.I_SIM, 'OperatorIdentifier')
        self.test.GetModem().GsmModem().Register(mccmnc)

        time.sleep(5)
        self.test.CheckResetCalled(True)

        # The new service should get marked as 'activated'.
        self.test.CheckServiceActivationState('activated')

class ActivatedDueToMdnTest(ActivationTest):
    """
    This test verifies that a valid MDN should cause the service to get marked
    as 'activated'.

    """
    def SetupTestModem(self):
        return ActivationTest.TestModem()

    def RunTest(self):
        # Service should appear as 'not-activated'.
        self.test.CheckServiceActivationState('not-activated')

        # Update the MDN. The service should get marked as activated.
        modem = self.test.GetModem()
        modem.PropertiesInterface().Set(mm1.I_MODEM,
                                        'OwnNumbers',
                                        ['1111111111'])
        time.sleep(5)
        self.test.CheckServiceActivationState('activated')

class network_LTEActivate(test.test):
    """
    After an online payment to activate a network, shill keeps track of service
    activation by monitoring changes to network registration and MDN updates
    combined with a modem reset. The test checks that the
    Cellular.ActivationState property of the service has the correct value
    associated with it by simulating possible scenarios using the pseudo modem
    manager.

    """
    version = 1

    def FindModem(self):
        """
        Tries to find a modem object exposed by the current modem manager and
        returns a proxy to it.

        @return A modem proxy, or None if not found.

        """
        try:
            manager, modem_path  = mm.PickOneModem('')
            return manager.GetModem(modem_path)
        except ValueError as e:
            # TODO(armansito): PickOneModem, for some predictably beautiful
            # reason, raises a ValueError instead of something more specific.
            # We should change that.
            logging.info('Error while getting modem: ' + repr(e))
            return None

    def GetModem(self):
        """
        Returns a modem proxy. This method will block for a LONG_TIMEOUT amount
        of time and retry to obtain a modem proxy until the timeout expires.

        """
        utils.poll_for_condition(
                lambda: self.FindModem() is not None,
                exception=error.TestFail('Modem not found.'),
                timeout=LONG_TIMEOUT)
        return self.FindModem()

    def GetModemState(self):
        """Returns the current ModemManager modem state."""
        modem = self.GetModem()
        props = modem.GetAll(mm1.I_MODEM)
        return props['State']

    def GetResetCalled(self, modem):
        """
        Returns the current value of the "ResetCalled" property of the current
        modem.

        @param modem: Modem proxy to send the query to.

        """
        return modem.GetAll(I_ACTIVATION_TEST)['ResetCalled']

    def _CheckResetCalledHelper(self, expected_value):
        modem = self.GetModem()
        try:
            return self.GetResetCalled(modem) == expected_value
        except dbus.exceptions.DBusException as e:
            name = e.get_dbus_name()
            unknown_method_str = 'org.feedesktop.DBus.Error.UnknownMethod'
            unknown_object_str = 'org.feedesktop.DBus.Error.UnknowObject'
            if name == unknown_method_str or name == unknown_object_str:
                return False
            raise e

    def CheckResetCalled(self, expected_value):
        """
        Checks that the ResetCalled property on the modem matches the expect
        value.

        @param expected_value: The expected value of ResetCalled.

        """
        utils.poll_for_condition(
            lambda: self._CheckResetCalledHelper(expected_value),
            exception=error.TestFail("\"ResetCalled\" did not match: " +
                                     str(expected_value)),
            timeout=LONG_TIMEOUT)

    def EnsureModemStateReached(self, expected_state, timeout):
        """
        Asserts that the underlying modem state becomes |expected_state| within
        |timeout|.

        @param expected_state: The expected modem state.
        @param timeout: Timeout in which the condition should be met.

        """
        utils.poll_for_condition(
                lambda: self.GetModemState() == expected_state,
                exception=error.TestFail(
                        'Modem failed to reach state ' +
                        mm1.ModemStateToString(expected_state)),
                timeout=timeout)

    def CheckServiceActivationState(self, expected_state):
        """
        Asserts that the service activation state matches |expected_state|
        within SHORT_TIMEOUT.

        @param expected_state: The expected service activation state.

        """
        logging.info('Checking for service activation state: %s',
                     expected_state)
        service = self.FindCellularService()
        success, state, duration = self.shill.wait_for_property_in(
            service,
            'Cellular.ActivationState',
            [expected_state],
            SHORT_TIMEOUT)
        if not success and state != expected_state:
            raise error.TestError(
                'Service activation state should be \'%s\', but it is \'%s\'.'
                % (expected_state, state))

    def FindCellularService(self, check_not_none=True):
        """
        Returns the current cellular service.

        @param check_not_none: If True, an error will be raised if no service
                was found.

        """
        if check_not_none:
            utils.poll_for_condition(
                    lambda: (self.shill.find_cellular_service_object() is
                             not None),
                    exception=error.TestError(
                            'Could not find cellular service within timeout.'),
                    timeout=LONG_TIMEOUT);

        service = self.shill.find_cellular_service_object()

        # Check once more, to make sure it's valid.
        if check_not_none and not service:
            raise error.TestError('Could not find cellular service.')
        return service

    def FindCellularDevice(self):
        """Returns the current cellular device."""
        device = self.shill.find_cellular_device_object()
        if not device:
            raise error.TestError('Could not find cellular device.')
        return device

    def ResetCellularDevice(self):
        """
        Resets all modems, guaranteeing that the operation succeeds and doesn't
        fail due to race conditions in pseudomodem start-up and test execution.

        """
        self.EnsureModemStateReached(
                mm1.MM_MODEM_STATE_ENABLED, SHORT_TIMEOUT)
        self.shill.reset_modem(self.FindCellularDevice())
        self.EnsureModemStateReached(
                mm1.MM_MODEM_STATE_ENABLED, SHORT_TIMEOUT)

    def run_once(self):
        with backchannel.Backchannel():
            self.sim = sim.SIM(sim.SIM.Carrier('test'),
                mm1.MM_MODEM_ACCESS_TECHNOLOGY_LTE)
            with pseudomodem.TestModemManagerContext(True,
                                                     sim=self.sim) as tmmc:
                self.shill = cellular_proxy.CellularProxy.get_proxy()
                self.shill.set_logging_for_cellular_test()

                tests = [
                    TimeoutResetTest(tmmc.GetPseudoModemManager(), self),
                    TimeoutActivatedTest(tmmc.GetPseudoModemManager(), self),
                    ResetAfterRegisterTest(tmmc.GetPseudoModemManager(), self),
                    ActivatedDueToMdnTest(tmmc.GetPseudoModemManager(), self)
                ]

                for test in tests:
                    test.Run()
