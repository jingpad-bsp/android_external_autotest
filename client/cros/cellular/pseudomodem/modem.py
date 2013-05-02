# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Pseudomodem implementation of the org.freedesktop.ModemManager1.Modem interface.
This class serves as the abstract base class of all fake modem implementations.

"""

import bearer
import dbus
import dbus.types
import dbus_std_ifaces
import disable_machine
import enable_machine
import gobject
import logging
import mm1
import modem_simple
import time

ALLOWED_BEARER_PROPERTIES = [
    'apn',
    'ip-type',
    'user',
    'password',
    'allow-roaming',
    'rm-protocol',
    'number'
]

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
            'PowerState' : dbus.types.UInt32(mm1.MM_MODEM_POWER_STATE_ON),

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

    @dbus.service.method(mm1.I_MODEM,
                         in_signature='b',
                         async_callbacks=('return_cb', 'raise_cb'))
    def Enable(self, enable, return_cb=None, raise_cb=None):
        if enable:
            logging.info('Modem enable')
            enable_machine.EnableMachine(self, return_cb, raise_cb).Step()
        else:
            logging.info('Modem disable')
            disable_machine.DisableMachine(self, return_cb, raise_cb).Step()

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
        The default implementation makes sure that all keys in properties are
        one of the allowed bearer properties. Subclasses can override this
        method to provide CDMA/3GPP specific checks.

        Raises:
            MMCoreError, if one or more properties are invalid.
        """
        for key in properties.iterkeys():
            if key not in ALLOWED_BEARER_PROPERTIES:
                raise mm1.MMCoreError(mm1.INVALID_ARGS,
                        'Invalid property "%s", not creating bearer.' % key)

    @dbus.service.method(mm1.I_MODEM, out_signature='ao')
    def ListBearers(self):
        logging.info('ListBearers')
        return [dbus.types.ObjectPath(key) for key in self.bearers.iterkeys()]

    @dbus.service.method(mm1.I_MODEM,
                         in_signature='a{sv}',
                         out_signature='o')
    def CreateBearer(self, properties):
        logging.info('CreateBearer')
        maxbearers = self.Get(mm1.I_MODEM, 'MaxBearers')
        if len(self.bearers) == maxbearers:
            raise mm1.MMCoreError(mm1.MMCoreError.TOO_MANY,
                    ('Maximum number of bearers reached. Cannot create new '
                     'bearer.'))
        else:
            self.ValidateBearerProperties(properties)
            bearer_obj = bearer.Bearer(self.bus, properties)
            logging.info('Created bearer with path "%s".' % bearer_obj.path)
            self.bearers[bearer_obj.path] = bearer_obj
            return bearer_obj.path

    def ActivateBearer(self, bearer_path):
        logging.info('ActivateBearer: %s', bearer_path)
        bearer = self.bearers.get(bearer_path, None)
        if bearer is None:
            message = 'Could not find bearer with path "%s"' % bearer_path
            logging.info(message)
            raise mm1.MMCoreError(mm1.MMCoreError.NOT_FOUND, message)

        max_active_bearers = self.Get(mm1.I_MODEM, 'MaxActiveBearers')
        if len(self.active_bearers) >= max_active_bearers:
            message = ('Cannot activate bearer: maximum active bearer count '
                       'reached.')
            logging.info(message)
            raise mm1.MMCoreError(mm1.MMCoreError.TOO_MANY, message)
        if bearer.IsActive():
            message = 'Bearer with path "%s" already active.', bearer_path
            logging.info(message)
            raise mm1.MMCoreError(mm1.MMCoreError.CONNECTED, message)

        self.active_bearers[bearer_path] = bearer
        bearer.Connect()

    def DeactivateBearer(self, bearer_path):
        logging.info('DeactivateBearer: %s' % bearer_path)
        bearer = self.bearers.get(bearer_path, None)
        if bearer is None:
            raise mm1.MMCoreError(mm1.MMCoreError.NOT_FOUND,
                'Could not find bearer with path "%s".' % bearer_path)
        if not bearer.IsActive():
            assert bearer_path not in self.active_bearers
            raise mm1.MMCoreError(mm1.MMCoreError.WRONG_STATE,
                'Bearer with path "%s" is not active.' % bearer_path)
        assert bearer_path in self.active_bearers
        bearer.Disconnect()
        self.active_bearers.pop(bearer_path)

    @dbus.service.method(mm1.I_MODEM, in_signature='o')
    def DeleteBearer(self, bearer):
        self.Disconnect(bearer)
        if bearer in self.bearers:
            self.bearers.pop(bearer)

    @dbus.service.method(mm1.I_MODEM)
    def Reset(self):
        logging.info('Resetting modem.')

        def RaiseCb(error):
            raise error

        def DisableEnable():
            self._properties = self._InitializeProperties()
            if self.sim:
                self.Set(mm1.I_MODEM,
                         'Sim',
                         dbus.types.ObjectPath(self.sim.path))
            # Shill will issue a second disable a little after the modem
            # becomes disabled (for fun of course). Wait here to make sure
            # that the enable is issued after the second disable fails.
            def DelayedEnable():
                self.Enable(True)
                return False
            gobject.timeout_add(3000, DelayedEnable)

        def ResetCleanup():
            logging.info('ResetCleanup')
            self.bearers.clear()
            self.Enable(False, DisableEnable, RaiseCb)

        if self.Get(mm1.I_MODEM, 'State') == mm1.MM_MODEM_STATE_CONNECTED:
            self.Disconnect('/', ResetCleanup, RaiseCb)
        else:
            ResetCleanup()

        # TODO(armansito): For now this is fine, but ideally the manager should
        # remove this modem object and create a brand new one.

    @dbus.service.method(mm1.I_MODEM, in_signature='s')
    def FactoryReset(self, code):
        pass

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
        return 'Bananas are tasty and fresh.'

    @dbus.service.method(mm1.I_MODEM, in_signature='u')
    def SetPowerState(self, power_state):
        self.SetUInt32(mm1.I_MODEM, 'PowerState', power_state);

    @dbus.service.signal(mm1.I_MODEM, signature='iiu')
    def StateChanged(self, old, new, reason):
        logging.info('Modem state changed from %u to %u for reason %u',
                old, new, reason)
