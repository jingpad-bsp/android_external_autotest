# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

import dbus
import dbus.types
import time

from autotest_lib.client.cros import backchannel, network, flimflam_test_path
from autotest_lib.client.cros.cellular import mm
from autotest_lib.client.cros.cellular.pseudomodem import modem_3gpp
from autotest_lib.client.cros.cellular.pseudomodem import mm1, pseudomodem, sim
import flimflam

I_ACTIVATION_TEST = 'Interface.LTEActivationTest'
ACTIVATION_REGISTRATION_TIMEOUT = 20
ACTIVATION_STATE_TIMEOUT = 10

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
        if self.test.flim.FindCellularService():
            self.test.CheckServiceActivationState('activated')

    def Run(self):
        """
        Configures the pseudomodem to run with the test modem, runs the test
        and cleans up.

        """
        if not self.test_modem:
            raise test.TestFail('Uninitialized test modem')
        self.pmm_context.SetModem(self.test_modem)
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
        network.ResetAllModems(self.test.flim)
        time.sleep(5)

        # The modem state should be ENABLED.
        if not self.test.GetModemState() == mm1.MM_MODEM_STATE_ENABLED:
            raise error.TestError('Modem should be in the ENABLED state.')

        # Service should appear as 'not-activated'.
        self.test.CheckServiceActivationState('not-activated')

        # Call 'CompleteActivation' on the device. The service should become
        # 'activating' and the modem should reset after 20 seconds.
        service = self.test.FindCellularService()
        service.CompleteCellularActivation()
        self.test.CheckServiceActivationState('activating')

        time.sleep(5)
        if self.test.GetModemResetCalled():
            raise error.TestError('Modem shouldn\'t have been reset.')

        # Wait until the register timeout.
        time.sleep(ACTIVATION_REGISTRATION_TIMEOUT)
        if not self.test.GetModemResetCalled():
            raise error.TestError('Modem should have been reset.')

        # At this point, a service should never get created.
        if self.test.flim.FindCellularService():
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
        network.ResetAllModems(self.test.flim)
        time.sleep(5)

        # The modem state should be ENABLED.
        if not self.test.GetModemState() == mm1.MM_MODEM_STATE_ENABLED:
            raise error.TestError('Modem should be in the ENABLED state.')

        # Service should appear as 'not-activated'.
        self.test.CheckServiceActivationState('not-activated')

        # Call 'CompleteActivation' on the device. The service should become
        # 'activating' and the modem should reset after 20 seconds.
        service = self.test.FindCellularService()
        service.CompleteCellularActivation()
        self.test.CheckServiceActivationState('activating')

        time.sleep(5)
        if self.test.GetModemResetCalled():
            raise error.TestError('Modem shouldn\'t have been reset.')

        # Wait until the register timeout.
        time.sleep(ACTIVATION_REGISTRATION_TIMEOUT)
        if not self.test.GetModemResetCalled():
            raise error.TestError('Modem should have been reset.')

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
                #   2. Triggered by ResetAllModems in
                #      ResetAfterRegisterTest.RunTest.
                self.register_count += 1
                if self.register_count > 2:
                    modem_3gpp.Modem3gpp.RegisterWithNetwork(
                            self, operator_id, return_cb, raise_cb)
        return Modem()

    def RunTest(self):
        network.ResetAllModems(self.test.flim)
        time.sleep(5)

        # The modem state should be ENABLED.
        if not self.test.GetModemState() == mm1.MM_MODEM_STATE_ENABLED:
            raise error.TestError('Modem should be in the ENABLED state.')

        # Service should appear as 'not-activated'.
        self.test.CheckServiceActivationState('not-activated')

        # Call 'CompleteActivation' on the device. The service should become
        # 'activating' and the modem should reset after 20 seconds.
        service = self.test.FindCellularService()
        service.CompleteCellularActivation()
        self.test.CheckServiceActivationState('activating')

        time.sleep(5)
        if self.test.GetModemResetCalled():
            raise error.TestError('Modem shouldn\'t have been reset.')

        # The service should register and trigger shill to reset the modem.
        mccmnc = self.test.sim.Get(mm1.I_SIM, 'OperatorIdentifier')
        self.test.GetModem().GsmModem().Register(mccmnc)

        time.sleep(5)
        if not self.test.GetModemResetCalled():
            raise error.TestError('Modem should have been reset.')

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
        network.ResetAllModems(self.test.flim)
        time.sleep(5)

        # The modem state should be ENABLED.
        if not self.test.GetModemState() == mm1.MM_MODEM_STATE_ENABLED:
            raise error.TestError('Modem should be in the ENABLED state.')

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

    def GetModem(self):
        """Returns a modem proxy."""
        manager, modem_path  = mm.PickOneModem('')
        return manager.GetModem(modem_path)

    def GetModemState(self):
        """Returns the current ModemManager modem state."""
        modem = self.GetModem()
        props = modem.GetAll(mm1.I_MODEM)
        return props['State']

    def GetModemResetCalled(self):
        """Returns True, if the modem has been reset at least once."""
        modem = self.GetModem()
        props = modem.GetAll(I_ACTIVATION_TEST)
        return props['ResetCalled']

    def CheckServiceActivationState(self, expected_state):
        """
        Asserts that the service activation state matches |expected_state|
        within ACTIVATION_STATE_TIMEOUT.

        @param expected_state: The expected service activation state.

        """
        service = self.FindCellularService()
        state = self.flim.WaitForServiceState(
            service=service,
            expected_states=[expected_state],
            timeout=ACTIVATION_STATE_TIMEOUT,
            property_name='Cellular.ActivationState')[0]
        if state != expected_state:
            raise error.TestError(
                'Service activation state should be \'%s\', but it is \'%s\'.'
                % (expected_state, state))

    def FindCellularService(self):
        """Returns the current cellular service."""
        service = self.flim.FindCellularService()
        if not service:
            raise error.TestError('Could not find cellular service.')
        return service

    def FindCellularDevice(self):
        """Returns the current cellular device."""
        device = self.flim.FindCellularDevice()
        if not device:
            raise error.TestError('Could not find cellular device.')
        return device

    def run_once(self):
        with backchannel.Backchannel():
            self.sim = sim.SIM(sim.SIM.Carrier('test'),
                mm1.MM_MODEM_ACCESS_TECHNOLOGY_LTE)
            with pseudomodem.TestModemManagerContext(True,
                                                     sim=self.sim) as tmmc:
                self.flim = flimflam.FlimFlam()
                self.device_manager = flimflam.DeviceManager(self.flim)
                self.flim.SetDebugTags(
                    'dbus+service+device+modem+cellular+portal+network+'
                    'manager+dhcp')

                tests = [
                    TimeoutResetTest(tmmc.GetPseudoModemManager(), self),
                    TimeoutActivatedTest(tmmc.GetPseudoModemManager(), self),
                    ResetAfterRegisterTest(tmmc.GetPseudoModemManager(), self),
                    ActivatedDueToMdnTest(tmmc.GetPseudoModemManager(), self)
                ]

                try:
                    self.device_manager.ShutdownAllExcept('cellular')
                    for test in tests:
                        test.Run()
                finally:
                    self.device_manager.RestoreDevices()
