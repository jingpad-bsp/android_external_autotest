# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import logging
import random
import time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import backchannel
from autotest_lib.client.cros.cellular import cell_tools
from autotest_lib.client.cros.cellular import emulator_config
from autotest_lib.client.cros.cellular import mm

# TODO(armansito): We should really move cros/cellular/pseudomodem/mm1.py to
# cros/cellular/, as it deprecates the old mm1.py. See crosbug.com/37005
from autotest_lib.client.cros.cellular.pseudomodem import mm1, pseudomodem, sim

from autotest_lib.client.cros import flimflam_test_path
import flimflam

# Number of seconds we wait for the cellular service to perform an action.
DEVICE_TIMEOUT=45
SERVICE_TIMEOUT=75

# Number of times and seconds between modem state checks to ensure that the
# modem is not in a temporary transition state.
NUM_MODEM_STATE_CHECKS=2
MODEM_STATE_CHECK_PERIOD_SECONDS=5

# Number of seconds to sleep after a connect request in slow-connect mode.
SLOW_CONNECT_WAIT_SECONDS=20


class TechnologyCommands():
    """Control the modem mostly using flimflam Technology interfaces."""
    def __init__(self, flim, command_delegate):
        self.flim = flim
        self.command_delegate = command_delegate

    def Enable(self):
        self.flim.EnableTechnology('cellular')

    def Disable(self):
        self.flim.DisableTechnology('cellular')

    def Connect(self, **kwargs):
        self.command_delegate.Connect(**kwargs)

    def Disconnect(self):
        return self.command_delegate.Disconnect()

    def __str__(self):
        return 'Technology Commands'


class ModemCommands():
    """Control the modem using modem manager DBUS interfaces."""
    def __init__(self, modem, slow_connect):
        self.modem = modem
        self.slow_connect = slow_connect

    def Enable(self):
        self.modem.Enable(True)

    def Disable(self):
        self.modem.Enable(False)

    def Connect(self, simple_connect_props):
        logging.debug('Connecting with properties: %r' % simple_connect_props)
        self.modem.Connect(simple_connect_props)
        if self.slow_connect:
            time.sleep(SLOW_CONNECT_WAIT_SECONDS)

    def Disconnect(self):
        """
        Disconnect Modem.

        Returns:
            True - to indicate that flimflam may autoconnect again.
        """
        try:
            self.modem.Disconnect()
        except dbus.exceptions.DBusException, e:
            if e._dbus_error_name == ('org.chromium.ModemManager'
                                      '.Error.OperationInitiated'):
                pass
            else:
                raise e
        return True

    def __str__(self):
        return 'Modem Commands'


class DeviceCommands():
    """Control the modem using flimflam device interfaces."""
    def __init__(self, flim, device, slow_connect):
        self.flim = flim
        self.device = device
        self.slow_connect = slow_connect
        self.service = None

    def GetService(self):
        service = self.flim.FindCellularService()
        if not service:
            raise error.TestFail(
                'Service failed to appear when using device commands.')
        return service

    def Enable(self):
        self.device.Enable(timeout=DEVICE_TIMEOUT)

    def Disable(self):
        self.service = None
        self.device.Disable(timeout=DEVICE_TIMEOUT)

    def Connect(self, **kwargs):
        self.GetService().Connect()
        if self.slow_connect:
            time.sleep(SLOW_CONNECT_WAIT_SECONDS)

    def Disconnect(self):
        """
        Disconnect Modem.

        Returns:
            False - to indicate that flimflam may not autoconnect again.
        """
        self.GetService().Disconnect()
        return False

    def __str__(self):
        return 'Device Commands'


class MixedRandomCommands():
    """Control the modem using a mixture of commands on device, modems, etc."""
    def __init__(self, commands_list):
        self.commands_list = commands_list

    def PickRandomCommands(self):
        return self.commands_list[random.randrange(len(self.commands_list))]

    def Enable(self):
        cmds = self.PickRandomCommands()
        logging.info('Enable with %s' % cmds)
        cmds.Enable()

    def Disable(self):
        cmds = self.PickRandomCommands()
        logging.info('Disable with %s' % cmds)
        cmds.Disable()

    def Connect(self, **kwargs):
        cmds = self.PickRandomCommands()
        logging.info('Connect with %s' % cmds)
        cmds.Connect(**kwargs)

    def Disconnect(self):
        cmds = self.PickRandomCommands()
        logging.info('Disconnect with %s' % cmds)
        return cmds.Disconnect()

    def __str__(self):
        return 'Mixed Commands'


class network_3GModemControl(test.test):
    version = 1

    def CompareModemPowerState(self, modem, expected_state):
        """Compare modem manager power state of a modem to an expected state."""
        return modem.IsEnabled() == expected_state

    def CompareDevicePowerState(self, device, expected_state):
        """Compare the flimflam device power state to an expected state."""
        device_properties = device.GetProperties(utf8_strings=True);
        state = device_properties['Powered']
        logging.info('Device Enabled = %s' % state)
        return state == expected_state

    def CompareServiceState(self, service, expected_states):
        """Compare the flimflam service state to a set of expected states."""
        if not service:
            logging.info('Service not found.')
            return False

        service_properties = service.GetProperties(utf8_strings=True);
        state = service_properties['State']
        logging.info('Service State = %s' % state)
        return state in expected_states

    def EnsureNotConnectingOrDisconnecting(self):
        """
        Ensure modem is not connecting or disconnecting.

        Raises:
            error.TestFail if it timed out waiting for the modem to finish
            connecting or disconnecting.
        """
        # Shill retries a failed connect attempt with a different APN so
        # check a few times to ensure the modem is not in between connect
        # attempts.
        for _ in range(NUM_MODEM_STATE_CHECKS):
            utils.poll_for_condition(
                lambda: not self.modem.IsConnectingOrDisconnecting(),
                error.TestFail('Timed out waiting for modem to finish ' +
                               'connecting or disconnecting.'),
                timeout=SERVICE_TIMEOUT)
            time.sleep(MODEM_STATE_CHECK_PERIOD_SECONDS)

    def EnsureDisabled(self):
        """
        Ensure modem disabled, device powered off, and no service.

        Raises:
            error.TestFail if the states are not consistent.
        """
        utils.poll_for_condition(
            lambda: self.CompareModemPowerState(self.modem, False),
            error.TestFail('Modem failed to enter state Disabled.'))
        utils.poll_for_condition(
            lambda: self.CompareDevicePowerState(self.device, False),
            error.TestFail('Device failed to enter state Powered=False.'))
        utils.poll_for_condition(
            lambda: not self.flim.FindCellularService(timeout=1),
            error.TestFail('Service should not be available.'),
            timeout=SERVICE_TIMEOUT)

    def EnsureEnabled(self, check_idle):
        """
        Ensure modem enabled, device powered and service exists.

        Args:
            check_idle: if True, then ensure that the service is idle
                        (i.e. not connected) otherwise ignore the
                        service state

        Raises:
            error.TestFail if the states are not consistent.
        """
        utils.poll_for_condition(
            lambda: self.CompareModemPowerState(self.modem, True),
            error.TestFail('Modem failed to enter state Enabled'))
        utils.poll_for_condition(
            lambda: self.CompareDevicePowerState(self.device, True),
            error.TestFail('Device failed to enter state Powered=True.'),
            timeout=30)

        if check_idle:
            utils.poll_for_condition(
                lambda: self.CompareServiceState(
                    self.flim.FindCellularService(timeout=SERVICE_TIMEOUT),
                    ['idle']),
                error.TestFail('Service failed to enter idle state.'),
                timeout=SERVICE_TIMEOUT)

    def EnsureConnected(self):
        """
        Ensure modem connected, device powered on, service connected.

        Raises:
            error.TestFail if the states are not consistent.
        """
        self.EnsureEnabled(check_idle=False)
        utils.poll_for_condition(
            lambda: self.CompareServiceState(self.flim.FindCellularService(),
                                             ['ready', 'portal', 'online']),
            error.TestFail('Service failed to connect.'),
            timeout=SERVICE_TIMEOUT)


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

        logging.info('Enabling')
        commands.Enable()
        self.EnsureEnabled(check_idle=not self.autoconnect)

        simple_connect_props = {'number': r'#777'}

        # Icera modems behave weirdly if we cancel the operation while the
        # modem is connecting. Work around the issue by waiting until the
        # connect operation completes.
        # TODO(benchan): Remove this workaround once the issue is addressed
        # on the modem side.
        self.EnsureNotConnectingOrDisconnecting()

        logging.info('Disabling')
        commands.Disable()
        self.EnsureDisabled()

        logging.info('Enabling again')
        commands.Enable()
        self.EnsureEnabled(check_idle=not self.autoconnect)

        if not self.autoconnect:
            logging.info('Connecting')
            commands.Connect(simple_connect_props=simple_connect_props)
        else:
            logging.info('Expecting AutoConnect to connect')
        self.EnsureConnected()

        logging.info('Disconnecting')
        will_autoreconnect = commands.Disconnect()

        if not (self.autoconnect and will_autoreconnect):
            # Icera modems behave weirdly if we cancel the operation while the
            # modem is disconnecting. Work around the issue by waiting until
            # the disconnect operation completes.
            # TODO(benchan): Remove this workaround once the issue is addressed
            # on the modem side.
            self.EnsureNotConnectingOrDisconnecting()

            self.EnsureEnabled(check_idle=True)
            logging.info('Connecting manually, since AutoConnect was on')
            commands.Connect(simple_connect_props=simple_connect_props)
        self.EnsureConnected()

        logging.info('Disabling')
        commands.Disable()
        self.EnsureDisabled()

    def run_once(self, autoconnect,
                 pseudo_modem=False,
                 mixed_iterations=2,
                 config=None, technology=None, slow_connect=False):
        # Use a backchannel so that flimflam will restart when the
        # test is over.  This ensures flimflam is in a known good
        # state even if this test fails.
        with backchannel.Backchannel():
            self.autoconnect = autoconnect

            if config and technology:
                bs, verifier = emulator_config.StartDefault(config, technology)
                cell_tools.PrepareModemForTechnology('', technology)

                # Clear all errors before we start.
                # Preparing the modem above may have caused some errors on the
                # 8960 (eg. lost connection, etc).
                bs.ClearErrors()

            fake_sim = sim.SIM(sim.SIM.Carrier('att'),
                mm1.MM_MODEM_ACCESS_TECHNOLOGY_GSM)
            with pseudomodem.TestModemManagerContext(pseudo_modem,
                                                     ['cromo', 'modemmanager'],
                                                     fake_sim):
                self.flim = flimflam.FlimFlam()

                # Enabling flimflam debugging makes it easier to debug
                # problems.  Tags will be cleared when the Backchannel
                # context exits and flimflam is restarted.
                self.flim.SetDebugTags(
                    'dbus+service+device+modem+cellular+portal+network+'
                    'manager+dhcp')

                self.device = self.flim.FindCellularDevice()
                if not self.device:
                    raise error.TestFail('Failed to find a cellular device.')
                manager, modem_path = mm.PickOneModem('')
                self.modem = manager.GetModem(modem_path)

                modem_commands = ModemCommands(self.modem, slow_connect)
                technology_commands = TechnologyCommands(self.flim,
                                                         modem_commands)
                device_commands = DeviceCommands(self.flim, self.device,
                                                 slow_connect)

                with cell_tools.AutoConnectContext(self.device, self.flim,
                                                   autoconnect):
                    # Get to a well known state.
                    self.flim.DisableTechnology('cellular')
                    self.EnsureDisabled()

                    self.TestCommands(technology_commands)
                    self.TestCommands(device_commands)
                    self.TestCommands(modem_commands)

                    # Run several times using commands mixed from each type
                    mixed = MixedRandomCommands([modem_commands,
                                                 technology_commands,
                                                 device_commands])
                    for _ in range(mixed_iterations):
                        self.TestCommands(mixed)
