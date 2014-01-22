# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import logging
import time

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.cellular import mm1_constants
from autotest_lib.client.cros.cellular.pseudomodem import modem_3gpp
from autotest_lib.client.cros.cellular.pseudomodem import pm_constants
from autotest_lib.client.cros.cellular.pseudomodem import pseudomodem
from autotest_lib.client.cros.cellular.pseudomodem import state_machine
from autotest_lib.client.cros.cellular.pseudomodem import state_machine_factory
from autotest_lib.client.cros.networking import cellular_proxy

# Used for software message propagation latencies.
SHORT_TIMEOUT_SECONDS = 2

STATE_MACHINE_SCAN = 'ScanMachine'
class ScanMachine(state_machine.StateMachine):
    """
    Handle shill initiated 3GPP scan request.

    A simple machine that allows the test to hook into the Scan asynchronous
    call.

    """
    # State machine states.
    SCAN_STATE = 'Scan'
    DONE_STATE = 'Done'

    def __init__(self, modem):
        super(ScanMachine, self).__init__(modem)
        self._state = ScanMachine.SCAN_STATE


    def _HandleScanState(self):
        """ The only real state in this machine. """
        self._modem.DoScan()
        self._state = ScanMachine.DONE_STATE
        return True


    def _GetCurrentState(self):
        return self._state


    def _GetModemStateFunctionMap(self):
        return {
                ScanMachine.SCAN_STATE: ScanMachine._HandleScanState,
                # ScanMachine.DONE_STATE is the final state. So, no handler.
        }


    def _ShouldStartStateMachine(self):
        return True


class TestStateMachineFactory(state_machine_factory.StateMachineFactory):
    """ Extend StateMachineFactory to create an interactive ScanMachine. """
    def ScanMachine(self, *args, **kwargs):
        """ Create a ScanMachine when needed in the modem. """
        machine = ScanMachine(*args, **kwargs)
        machine.EnterInteractiveMode(self._bus)
        return machine


class AsyncScanModem(modem_3gpp.Modem3gpp):
    """ 3GPP modem that uses ScanMachine for the Scan call. """
    def Scan(self, return_cb, raise_cb):
        """ Overriden from Modem3gpp. """
        # Stash away the scan_ok callback for when the Scan finishes.
        logging.debug('Network scan initiated.')
        self._scan_ok_callback = return_cb
        self._scan_failed_callback = raise_cb
        self._scan_machine = self._state_machine_factory.ScanMachine(self)
        self._scan_machine.Start()


    def DoScan(self):
        """ Defer to Modem3gpp to take the original |SyncScan| action. """
        # We're done scanning, drop |_scan_machine| reference.
        self._scan_machine = None
        try:
            scan_result = super(AsyncScanModem, self).SyncScan()
        except dbus.exceptions.DBusException as e:
            logging.warning('Network scan failed')
            self._scan_failed_callback(e)
            return

        logging.debug('Network scan completed.')
        self._scan_ok_callback(scan_result)


class network_3GScanningProperty(test.test):
    """
    Test that the |Scanning| Property of the shill cellular device object is
    updated correctly in the following two scenarios:
      (1) When a user requests a network scan using the |ProposeScan| method of
          the cellular device.
      (2) During the initial modem enable-register-connect sequence.

    """
    version = 1

    def _find_mm_modem(self):
        """
        Find the modemmanager modem object.

        Assumption: There is only one modem in the system.

        @raises: TestError unless exactly one modem is found.

        """
        object_manager = dbus.Interface(
                self._bus.get_object(mm1_constants.I_MODEM_MANAGER,
                                     mm1_constants.MM1),
                mm1_constants.I_OBJECT_MANAGER)
        try:
            modems = object_manager.GetManagedObjects()
        except dbus.exceptions.DBusException as e:
            raise error.TestFail('Failed to list the available modems. '
                                 'DBus error: |%s|', repr(e))
        if len(modems) != 1:
            raise error.TestFail('Expected one modem object, found %d' %
                                 len(modems))

        modem_path = modems.keys()[0]
        modem_object = self._bus.get_object(mm1_constants.I_MODEM_MANAGER,
                                            modem_path)
        # Check that this object is valid
        try:
            modem_object.GetAll(mm1_constants.I_MODEM,
                                dbus_interface=mm1_constants.I_PROPERTIES)
        except dbus.exceptions.DBusException as e:
            raise error.TestFail('Failed to obtain dbus object for the modem '
                                 'DBus error: |%s|', repr(e))

        return dbus.Interface(modem_object, mm1_constants.I_MODEM)


    def _check_mm_state(self, modem, states):
        """
        Verify that the modemmanager state is |state|.

        @param modem: A DBus object for the modemmanager modem.
        @param states: The expected state of the modem. This is either a single
                state, or a list of states.
        @raises: TestError if the state differs.
        """
        if not isinstance(states, list):
            states = [states]
        properties = modem.GetAll(mm1_constants.I_MODEM,
                                  dbus_interface=mm1_constants.I_PROPERTIES)
        actual_state = properties[mm1_constants.MM_MODEM_PROPERTY_NAME_STATE]
        if actual_state not in states:
            state_names = [mm1_constants.ModemStateToString(x) for x in states]
            raise error.TestFail(
                    'Expected modemmanager modem state to be one of %s but '
                    'found %s' %
                    (state_names,
                     mm1_constants.ModemStateToString(actual_state)))


    def _check_shill_property_update(self, cellular_device, property_name,
                                     old_state, new_state):
        """
        Check the value of property of shill.

        @param cellular_device: The DBus proxy object for the cellular device.
        @param property_name: Name of the property to check.
        @param old_state: old value of property.
        @param new_state: new expected value of property.
        @raises: TestError if the property fails to enter the given state.

        """
        # If we don't expect a change in the value, there is a race between this
        # check and a possible (erronous) update of the value. Allow some time
        # for the property to be updated before checking.
        if old_state == new_state:
            time.sleep(SHORT_TIMEOUT_SECONDS)
            polling_timeout = 0
        else:
            polling_timeout = SHORT_TIMEOUT_SECONDS
        success, _, _ = self._cellular_proxy.wait_for_property_in(
                cellular_device,
                property_name,
                (new_state,),
                timeout_seconds=polling_timeout)
        if not success:
            raise error.TestFail('Shill failed to set |%s| to %s.' %
                                 (property_name, str(new_state)))


    def _itesting_machine(self, machine_name, timeout=SHORT_TIMEOUT_SECONDS):
        """
        Get the testing interface of the given interactive state machine.

        @param machine_name: The name of the interactive state machine.
        @return dbus.Interface for the testing interface of
                InteractiveScanningMachine, if found. None otherwise.
        @raises utils.TimeoutError if a valid dbus object can't be found.

        """
        def _get_machine():
            machine = self._bus.get_object(
                    mm1_constants.I_MODEM_MANAGER,
                    '/'.join([pm_constants.TESTING_PATH, machine_name]))
            if machine:
                i_machine = dbus.Interface(machine, pm_constants.I_TESTING_ISM)
                # Only way to know if this DBus object is valid is to call a
                # method on it.
                try:
                    i_machine.IsWaiting()  # Ignore result.
                    return i_machine
                except dbus.exceptions.DBusException as e:
                    logging.debug(e)
                    return None

        utils.poll_for_condition(_get_machine, timeout=timeout)
        return _get_machine()


    def test_user_initiated_cellular_scan(self):
        """
        Test that the |ProposeScan| DBus method exported by shill cellular
        object correctly updates the cellular object |Scanning| property while
        the scan is in progress.
        """
        test_modem = AsyncScanModem(
                state_machine_factory=TestStateMachineFactory())
        with pseudomodem.TestModemManagerContext(True,
                                                 family='3GPP',
                                                 modem=test_modem):
            self._cellular_proxy = cellular_proxy.CellularProxy.get_proxy()
            self._bus = dbus.SystemBus()
            self._cellular_proxy.set_logging_for_cellular_test()

            logging.info('Sanity check initial values')
            utils.poll_for_condition(
                    self._cellular_proxy.find_cellular_device_object,
                    exception=error.TestFail(
                            'Bad initial state: Failed to obtain a cellular '
                            'device in pseudomodem context.'),
                    timeout=SHORT_TIMEOUT_SECONDS)
            device = self._cellular_proxy.find_cellular_device_object()
            try:
                self._itesting_machine(STATE_MACHINE_SCAN, 0)
                raise error.TestFail('Bad initial state: scan machine created '
                                     'by pseudomodem before scan is proposed.')
            except utils.TimeoutError:
                pass

            self._check_shill_property_update(
                    device,
                    self._cellular_proxy.DEVICE_PROPERTY_SCANNING,
                    False,
                    False)

            logging.info('Test actions and checks')
            device.ProposeScan()
            try:
                itesting_scan_machine = self._itesting_machine(
                        STATE_MACHINE_SCAN)
            except utils.TimeoutError:
                raise error.TestFail('Pseudomodem failed to launch %s' %
                                     STATE_MACHINE_SCAN)
            utils.poll_for_condition(
                    itesting_scan_machine.IsWaiting,
                    exception=error.TestFail('Scan machine failed to enter '
                                             'scan state'),
                    timeout=SHORT_TIMEOUT_SECONDS)
            self._check_shill_property_update(
                    device,
                    self._cellular_proxy.DEVICE_PROPERTY_SCANNING,
                    False,
                    True)

            itesting_scan_machine.Advance()
            utils.poll_for_condition(
                    lambda: not itesting_scan_machine.IsWaiting(),
                    exception=error.TestFail('Scan machine failed to exit '
                                             'scan state'),
                    timeout=SHORT_TIMEOUT_SECONDS)
            self._check_shill_property_update(
                    device,
                    self._cellular_proxy.DEVICE_PROPERTY_SCANNING,
                    True,
                    False)


    def test_activated_service_states(self):
        """
        Test that shill |Scanning| property is updated correctly when an
        activated 3GPP service connects.
        """
        sm_factory = state_machine_factory.StateMachineFactory()
        sm_factory.SetInteractive(pm_constants.STATE_MACHINE_ENABLE)
        sm_factory.SetInteractive(pm_constants.STATE_MACHINE_REGISTER)
        with pseudomodem.TestModemManagerContext(True,
                                                 family='3GPP',
                                                 sm_factory=sm_factory):
            self._cellular_proxy = cellular_proxy.CellularProxy.get_proxy()
            self._bus = dbus.SystemBus()
            self._cellular_proxy.set_logging_for_cellular_test()

            logging.info('Sanity check initial values')
            enable_machine = self._itesting_machine(
                    pm_constants.STATE_MACHINE_ENABLE)
            utils.poll_for_condition(
                    enable_machine.IsWaiting,
                    exception=error.TestFail(
                            'Bad initial state: Pseudomodem did not launch '
                            'Enable machine'),
                    timeout=SHORT_TIMEOUT_SECONDS)
            utils.poll_for_condition(
                    self._cellular_proxy.find_cellular_device_object,
                    exception=error.TestFail(
                            'Bad initial state: Failed to obtain a cellular '
                            'device in pseudomodem context.'),
                    timeout=SHORT_TIMEOUT_SECONDS)
            device = self._cellular_proxy.find_cellular_device_object()
            mm_modem = self._find_mm_modem()

            logging.info('Test Connect sequence')
            self._check_mm_state(mm_modem,
                                 mm1_constants.MM_MODEM_STATE_DISABLED)
            self._check_shill_property_update(
                    device,
                    self._cellular_proxy.DEVICE_PROPERTY_POWERED,
                    False,
                    False)
            self._check_shill_property_update(
                    device,
                    self._cellular_proxy.DEVICE_PROPERTY_SCANNING,
                    False,
                    False)
            logging.info('Expectation met: |Scanning| is False in MM state '
                         'Disabled')
            enable_machine.Advance()

            # MM state: Enabling
            utils.poll_for_condition(
                    enable_machine.IsWaiting,
                    exception=error.TestFail('EnableMachine failed to wait in '
                                             'Enabling state'),
                    timeout=SHORT_TIMEOUT_SECONDS)
            self._check_mm_state(mm_modem,
                                 mm1_constants.MM_MODEM_STATE_ENABLING)
            self._check_shill_property_update(
                    device,
                    self._cellular_proxy.DEVICE_PROPERTY_SCANNING,
                    False,
                    True)
            logging.info('Expectation met: |Scanning| is True in MM state '
                         'Enabling')
            enable_machine.Advance()

            # MM state: Enabled
            utils.poll_for_condition(
                    enable_machine.IsWaiting,
                    exception=error.TestFail('EnableMachine failed to wait in '
                                             'Enabled state'),
                    timeout=SHORT_TIMEOUT_SECONDS)
            # Finish the enable call.
            enable_machine.Advance()

            self._check_mm_state(mm_modem, mm1_constants.MM_MODEM_STATE_ENABLED)
            self._check_shill_property_update(
                    device,
                    self._cellular_proxy.DEVICE_PROPERTY_POWERED,
                    False,
                    True)
            self._check_shill_property_update(
                    device,
                    self._cellular_proxy.DEVICE_PROPERTY_SCANNING,
                    True,
                    True)

            register_machine = self._itesting_machine(
                    pm_constants.STATE_MACHINE_REGISTER)
            utils.poll_for_condition(
                    register_machine.IsWaiting,
                    exception=error.TestFail('SearchingMachine failed to wait '
                                             'in Enabled state'),
                    timeout=SHORT_TIMEOUT_SECONDS)
            logging.info('Expectation met: |Scanning| is True in MM state '
                         'Enabled')
            register_machine.Advance()

            # MM state: Searching
            utils.poll_for_condition(
                    register_machine.IsWaiting,
                    exception=error.TestFail('SearchingMachine failed to wait '
                                             'in Searching state'),
                    timeout=SHORT_TIMEOUT_SECONDS)
            self._check_mm_state(mm_modem,
                                 mm1_constants.MM_MODEM_STATE_SEARCHING)
            enable_machine.Advance()
            self._check_shill_property_update(
                    device,
                    self._cellular_proxy.DEVICE_PROPERTY_SCANNING,
                    True,
                    True)
            logging.info('Expectation met: |Scanning| is True in MM state '
                         'Searching')
            register_machine.Advance()

            # MM state: >= Registered
            utils.poll_for_condition(
                    self._cellular_proxy.find_cellular_service_object,
                    error.TestFail('Failed to create Cellular Service for a '
                                   'registered modem'),
                    timeout=SHORT_TIMEOUT_SECONDS)
            self._check_mm_state(
                    mm_modem,
                    [mm1_constants.MM_MODEM_STATE_REGISTERED,
                     mm1_constants.MM_MODEM_STATE_CONNECTING,
                     mm1_constants.MM_MODEM_STATE_CONNECTED])
            self._check_shill_property_update(
                    device,
                    self._cellular_proxy.DEVICE_PROPERTY_SCANNING,
                    True,
                    False)
            logging.info('Expectation met: |Scanning| is False in MM state '
                         'Registered')


    def run_once(self, test_name):
        """ Autotest entry function """
        # TODO(pprabhu) Run both of these tests after crbug.com/328257 is fixed.
        if test_name == 'user_initiated_cellular_scan':
            self.test_user_initiated_cellular_scan()
        elif test_name == 'activated_service_states':
            self.test_activated_service_states()
        else:
            raise error.TestFail('Unknown test_name')
