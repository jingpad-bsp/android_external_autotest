# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus, logging, time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import backchannel
from autotest_lib.client.cros.cellular import cell_tools

from autotest_lib.client.cros import flimflam_test_path
import flimflam
import mm


class TechnologyCommands():
    """Control the modem mostly using flimflam Technology interfaces."""
    def __init__(self, flim, command_delegate):
        self.flim = flim
        self.command_delegate = command_delegate

    def Enable(self):
        self.flim.EnableTechnology('cellular')

    def Disable(self):
        self.flim.DisableTechnology('cellular')

    def Connect(self):
        self.command_delegate.Connect()

    def Disconnect(self):
        self.command_delegate.Disconnect()

    def __str__(self):
        return 'Technology Commands'


class ModemCommands():
    """Control the modem using modem manager DBUS interfaces."""
    def __init__(self, modem, simple_modem):
        self.modem = modem
        self.simple_modem = simple_modem

    def Enable(self):
        self.modem.Enable(True)

    def Disable(self):
        self.modem.Enable(False)

    def Connect(self):
        connect_props = {'number': r'#777'}
        self.simple_modem.Connect(connect_props)

    def Disconnect(self):
        try:
            self.modem.Disconnect()
        except dbus.exceptions.DBusException, e:
            if e._dbus_error_name == ('org.chromium.ModemManager'
                                      '.Error.OperationInitiated'):
                pass
            else:
                raise e

    def __str__(self):
        return 'Modem Commands'


class DeviceCommands():
    """Control the modem using flimflam device interfaces."""
    def __init__(self, flim, device):
        self.flim = flim
        self.device = device
        self.service = None

    def Enable(self):
        self.device.SetProperty('Powered', True)

    def Disable(self):
        self.service = None
        self.device.SetProperty('Powered', False)

    def Connect(self):
        service = self.flim.FindCellularService()
        if not service:
            raise error.TestFail('Service failed to appear when '
                                 'using device commands.')
        service.Connect()
        self.service = service

    def Disconnect(self):
        self.service.Disconnect()
        self.service = None

    def __str__(self):
        return 'Device Commands'


class network_3GModemControl(test.test):
    version = 1

    def CompareModemPowerState(self, manager, path, expected_state):
        """Compare modem manager power state of a modem to an expected state."""
        props = manager.Properties(path)
        state = props['Enabled']
        logging.info('Modem Enabled = %s' % state)
        return state == expected_state

    def CompareDevicePowerState(self, device, expected_state):
        """Compare the flimflam device power state to an expected state."""
        device_properties = device.GetProperties(utf8_strings=True);
        state = device_properties['Powered']
        logging.info('Device Enabled = %s' % state)
        return state == expected_state

    def CompareServiceState(self, service, expected_states):
        """Compare the flimflam service state to a set of expected states."""
        service_properties = service.GetProperties(utf8_strings=True);
        state = service_properties['State']
        logging.info('Service State = %s' % state)
        return state in expected_states

    def EnsureDisabled(self):
        """
        Ensure modem disabled, device powered off, and no service.

        Raises:
            error.TestFail if the states are not consistent.
        """
        utils.poll_for_condition(
            lambda: self.CompareModemPowerState(self.modem_manager,
                                                self.modem_path, False),
            error.TestFail('Modem failed to enter state Disabled.'))
        utils.poll_for_condition(
            lambda: self.CompareDevicePowerState(self.device, False),
            error.TestFail('Device failed to enter state Powered=False.'))
        utils.poll_for_condition(
            lambda: not self.flim.FindCellularService(timeout=1),
            error.TestFail('Service should not be available.'))

    def EnsureEnabled(self):
        """
        Ensure modem enabled, device powered on, and service idle.

        Raises:
            error.TestFail if the states are not consistent
        """
        utils.poll_for_condition(
            lambda: self.CompareModemPowerState(self.modem_manager,
                                                self.modem_path, True),
            error.TestFail('Modem failed to enter state Enabled'))
        utils.poll_for_condition(
            lambda: self.CompareDevicePowerState(self.device, True),
            error.TestFail('Device failed to enter state Powered=True.'))
        # wait for service to appear and then enter idle state
        service = self.flim.FindCellularService()
        if not service:
            error.TestFail('Service failed to appear for enabled modem.')
        utils.poll_for_condition(
            lambda: self.CompareServiceState(service, ['idle']),
            error.TestFail('Service failed to enter idle state.'))

    def EnsureConnected(self):
        """
        Ensure modem connected, device powered on, service connected.

        Raises:
            error.TestFail if the states are not consistent.
        """
        utils.poll_for_condition(
            lambda: self.CompareModemPowerState(self.modem_manager,
                                                self.modem_path, True),
            error.TestFail('Modem failed to enter state Enabled'))
        utils.poll_for_condition(
            lambda: self.CompareDevicePowerState(self.device, True),
            error.TestFail('Device failed to enter state Powered=True.'))
        # wait for service to appear and then enter a connected state
        service = self.flim.FindCellularService()
        if not service:
            error.TestFail('Service failed to appear for connected modem.')
        utils.poll_for_condition(
            lambda: self.CompareServiceState(service,
                                             ['ready', 'portal', 'online']),
            error.TestFail('Service failed to connect.'))

    def TestCommands(self, commands):
        """
        Manipulate the modem using modem, device or technology commands.

        Changes the state of the modem in various ways including
        disable while connected and then verifies the state of the
        modem manager and flimflam.

        Raises:
            error.TestFail if the states are not consistent.

        """
        logging.info('Testing using %s' % commands)
        commands.Enable()
        self.EnsureEnabled()
        commands.Disable()
        self.EnsureDisabled()
        commands.Enable()
        self.EnsureEnabled()
        commands.Connect()
        self.EnsureConnected()
        commands.Disconnect()
        self.EnsureEnabled()
        commands.Connect()
        self.EnsureConnected()
        commands.Disable()
        self.EnsureDisabled()

    def run_once(self, connect_count=10, maximum_avg_assoc_time_seconds=5):
        # Use a backchannel so that flimflam will restart when the
        # test is over.  This ensures flimflam is in a known good
        # state even if this test fails.
        with backchannel.Backchannel():
            self.flim = flimflam.FlimFlam()
            self.device = self.flim.FindCellularDevice()
            self.modem_manager, self.modem_path = mm.PickOneModem('')
            self.modem = self.modem_manager.Modem(self.modem_path)
            self.simple_modem = self.modem_manager.SimpleModem(self.modem_path)

            modem_commands = ModemCommands(self.modem, self.simple_modem)
            technology_commands = TechnologyCommands(self.flim,
                                                     modem_commands)
            device_commands = DeviceCommands(self.flim, self.device)

            with cell_tools.DisableAutoConnectContext(self.device, self.flim):
                # Get to a well known state.
                self.flim.DisableTechnology('cellular')
                self.EnsureDisabled()

                self.TestCommands(modem_commands)
                self.TestCommands(technology_commands)
                self.TestCommands(device_commands)
