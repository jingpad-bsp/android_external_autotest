# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Pseudomodem implementation of the org.freedesktop.ModemManager1.Modem interface.
This class serves as the abstract base class of all fake modem implementations.
"""

import dbus
import dbus.types
import dbus_std_ifaces
import gobject
import logging
import mm1
import modem_simple

class Modem(dbus_std_ifaces.DBusProperties, modem_simple.ModemSimple):
    # TODO(armansito): Implement something similar to a delegate interface
    # that can be provided by tests to fine tune the state transitions.
    # The delegate should be able to receive callbacks between state
    # transitions
    class StateMachine(object):
        def __init__(self, modem):
            self.modem = modem
            self.cancelled = False

        def Step(self):
            raise NotImplementedError()

        def Cancel(self):
            self.cancelled = True

    class EnableStep(StateMachine):
        """
        Handles the modem enable state transitions.

        """
        def Cancel(self):
            super(Modem.EnableStep, self).Cancel()

        def Step(self):
            if self.cancelled:
                self.modem.enable_step = None
                return

            state = self.modem.Get(mm1.I_MODEM, 'State')
            if self.modem.enable_step:
                if self.modem.enable_step != self:
                    logging.info('There is an ongoing Enable operation.')
                    # A new enable request has been received,
                    # raise the appropriate error.
                    if state == mm1.MM_MODEM_STATE_ENABLING:
                        message = 'Modem enable already in progress.'
                    else:
                        message = ('Modem enable has already been initiated'
                                   ', ignoring.')
                    raise mm1.MMCoreError(mm1.MMCoreError.IN_PROGRESS, message)
            else:
                # TODO(armansito): If we want an Enable request to cancel
                # a pending disable, we should do so here.

                # A new enable process is being initiated and no other
                # enable in progress
                if state != mm1.MM_MODEM_STATE_DISABLED:
                    raise mm1.MMCoreError(
                        mm1.MMCoreError.WRONG_STATE,
                        'Modem cannot be enabled if not in disabled state.')
                # Set this as the enabling operation
                logging.info('Starting Enable.')
                self.modem.enable_step = self

            reason = mm1.MM_MODEM_STATE_CHANGE_REASON_USER_REQUESTED

            if state == mm1.MM_MODEM_STATE_DISABLED:
                assert self.modem.disable_step is None
                assert self.modem.connect_step is None
                assert self.modem.disconnect_step is None
                logging.info('EnableStep: Setting state to ENABLING.')
                self.modem.ChangeState(mm1.MM_MODEM_STATE_ENABLING, reason)
                gobject.idle_add(Modem.EnableStep.Step, self)
            elif state == mm1.MM_MODEM_STATE_ENABLING:
                assert self.modem.disable_step is None
                assert self.modem.connect_step is None
                assert self.modem.disconnect_step is None
                logging.info('EnableStep: Setting state to ENABLED.')
                self.modem.ChangeState(mm1.MM_MODEM_STATE_ENABLED, reason)
                gobject.idle_add(Modem.EnableStep.Step, self)
            elif state == mm1.MM_MODEM_STATE_ENABLED:
                assert self.modem.disable_step is None
                assert self.modem.connect_step is None
                assert self.modem.disconnect_step is None
                logging.info('EnableStep: Searching for networks.')
                self.modem.enable_step = None
                self.modem.RegisterWithNetwork()

    def __init__(self, bus=None,
                 device='pseudomodem0',
                 name='/Modem/0',
                 roaming_networks=[],
                 config=None):
        """
        Initializes the fake modem object. kwargs can contain the optional
        argument |config|, which is a dictionary of property-value mappings.
        These properties will be added to the underlying property dictionary,
        and must be one of the properties listed in the ModemManager Reference
        Manual. See _InitializeProperties for all of the properties that belong
        to this interface. Possible values for each are enumerated in mm1.py

        """

        self.device = device

        # The superclass construct will call _InitializeProperties
        dbus_std_ifaces.DBusProperties.__init__(self,
            mm1.MM1 + name, bus, config)

        self.roaming_networks = roaming_networks

        self.bearers = {}
        self.active_bearers = {}
        self.sim = None
        self.enable_step = None
        self.disable_step = None
        self.connect_step = None
        self.disconnect_step = None
        self.register_step = None

    def _InitializeProperties(self):
        """
        Sets up the default values for the properties

        """
        props = {
            'Manufacturer' : 'Banana Technologies', # be creative here
            'Model' : 'Banana Peel 3000', # yep
            'Revision' : '1.0',
            'DeviceIdentifier' : 'Banana1234567890',
            'Device' : self.device,
            'Drivers' : ['FakeDriver'],
            'Plugin' : 'Banana Plugin',
            'UnlockRequired' : dbus.types.UInt32(mm1.MM_MODEM_LOCK_NONE),
            'UnlockRetries' : {
                dbus.types.UInt32(mm1.MM_MODEM_LOCK_SIM_PIN) : (
                    dbus.types.UInt32(3))
            },
            'State' : dbus.types.Int32(mm1.MM_MODEM_STATE_DISABLED),
            'SignalQuality' : dbus.types.Struct(
                                      [dbus.types.UInt32(100), True],
                                      signature='ub'),
            'OwnNumbers' : ['5555555555'],

            # specified by subclass:
            'ModemCapabilities' :
                dbus.types.UInt32(mm1.MM_MODEM_CAPABILITY_NONE),
            'CurrentCapabilities' :
                dbus.types.UInt32(mm1.MM_MODEM_CAPABILITY_NONE),
            'MaxBearers' : dbus.types.UInt32(0),
            'MaxActiveBearers' : dbus.types.UInt32(0),
            'EquipmentIdentifier' : '',
            'AccessTechnologies' :
                    dbus.types.UInt32(mm1.MM_MODEM_ACCESS_TECHNOLOGY_UNKNOWN),
            'SupportedModes' : dbus.types.UInt32(mm1.MM_MODEM_MODE_NONE),
            'AllowedModes' : dbus.types.UInt32(mm1.MM_MODEM_MODE_NONE),
            'PreferredMode' : dbus.types.UInt32(mm1.MM_MODEM_MODE_NONE),
            'SupportedBands' : [dbus.types.UInt32(mm1.MM_MODEM_BAND_UNKNOWN)],
            'Bands' : [dbus.types.UInt32(mm1.MM_MODEM_BAND_UNKNOWN)],
            'Sim' : dbus.types.ObjectPath(mm1.ROOT_PATH)
        }
        return { mm1.I_MODEM : props }

    def IsPendingEnable(self):
        return self.enable_step and not self.enable_step.cancelled

    def IsPendingDisable(self):
        return self.disable_step and not self.disable_step.cancelled

    def IsPendingConnect(self):
        return self.connect_step and not self.connect_step.cancelled

    def IsPendingDisconnect(self):
        return self.disconnect_step and not self.disconnect_step.cancelled

    def IsPendingRegister(self):
        return self.register_step and not self.register_step.cancelled

    def SetSignalQuality(self, quality):
        self.Set(mm1.I_MODEM, 'SignalQuality', (dbus.types.Struct(
            [dbus.types.UInt32(quality), True], signature='ub')))

    def ChangeState(self, state, reason):
        old_state = self.Get(mm1.I_MODEM, 'State')
        self.SetInt32(mm1.I_MODEM, 'State', state)
        self.StateChanged(old_state, state, dbus.types.UInt32(reason))

    def SetSIM(self, sim):
        self.sim = sim
        if not sim:
            val = mm1.ROOT_PATH
        else:
            val = sim.path
            self.sim.SetBus(self.bus)
        self.Set(mm1.I_MODEM, 'Sim', dbus.types.ObjectPath(val))

    @dbus.service.method(mm1.I_MODEM, in_signature='b')
    def Enable(self, enable):
        if enable:
            logging.info('Modem enable')
            Modem.EnableStep(self).Step()
        else:
            logging.info('Modem disable')
            Modem.DisableStep(self).Step()

    def RegisterWithNetwork(self):
        """
        Register with the current home network, as specified
        in the constructor. Must set the state to SEARCHING first,
        and see if there is a home network available. Technology
        specific error cases need to be handled here (such as activation,
        the presence of a valid SIM card, etc)

        Must be implemented by a subclass.

        """
        raise NotImplementedError()

    def UnregisterWithNetwork(self):
        """
        Unregisters with the home network. This should transition
        the modem into the ENABLED state

        Must be implemented by a subclass

        """
        raise NotImplementedError()

    def ValidateBearerProperties(self, properties):
        """
        Must be implemented by subclasses.

        Returns:
            True, if properties are valid for the given access technologies.

        Raises:
            MMCoreError, if one or more properties are invalid.
        """
        raise NotImplementedError()

    @dbus.service.method(mm1.I_MODEM, out_signature='ao')
    def ListBearers(self):
        raise NotImplementedError()

    @dbus.service.method(mm1.I_MODEM,
                         in_signature='a{sv}',
                         out_signature='o')
    def CreateBearer(self, properties):
        raise NotImplementedError()

    @dbus.service.method(mm1.I_MODEM, in_signature='o')
    def DeleteBearer(self, bearer):
        raise NotImplementedError()

    @dbus.service.method(mm1.I_MODEM)
    def Reset(self):
        raise NotImplementedError()

    @dbus.service.method(mm1.I_MODEM, in_signature='s')
    def FactoryReset(self, code):
        raise NotImplementedError()

    @dbus.service.method(mm1.I_MODEM, in_signature='uu')
    def SetAllowedModes(self, modes, preferred):
        self.SetUInt32(mm1.I_MODEM, 'AllowedModes', modes)
        self.SetUInt32(mm1.I_MODEM, 'PreferredMode', preferred)

    @dbus.service.method(mm1.I_MODEM, in_signature='au')
    def SetBands(self, bands):
        band_list = [dbus.types.UInt32(band) for band in bands]
        self.Set(mm1.I_MODEM, 'Bands', band_list)

    @dbus.service.method(mm1.I_MODEM,
                         in_signature='su',
                         out_signature='s')
    def Command(self, cmd, timeout):
        raise NotImplementedError()

    @dbus.service.signal(mm1.I_MODEM, signature='iiu')
    def StateChanged(self, old, new, reason):
        logging.info('Modem state changed from %u to %u for reason %u',
                old, new, reason)
