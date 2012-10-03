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
import mm1

class Modem(dbus_std_ifaces.DBusProperties):

    def __init__(self, bus,
                 device='pseudomodem0',
                 name='/Modem/0',
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
        dbus_std_ifaces.DBusProperties.__init__(self, bus, mm1.MM1 + name)

        # Custom properties will be set here
        if config:
            self._properties.upddate(config)

        self.bearers = []
        self.sim = None

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
                mm1.MM_MODEM_LOCK_SIM_PIN : dbus.types.UInt32(3)
            },
            'State' : dbus.types.UInt32(mm1.MM_MODEM_STATE_DISABLED),
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
                    dbus.types.UInt32(mm1.MM_ACCESS_TECHNOLOGY_UNKNOWN),
            'SupportedModes' : dbus.types.UInt32(mm1.MM_MODEM_MODE_NONE),
            'AllowedModes' : dbus.types.UInt32(mm1.MM_MODEM_MODE_NONE),
            'PreferredMode' : dbus.types.UInt32(mm1.MM_MODEM_MODE_NONE),
            'SupportedBands' : [dbus.types.UInt32(mm1.MM_MODEM_BAND_UNKNOWN)],
            'Bands' : [dbus.types.UInt32(mm1.MM_MODEM_BAND_UNKNOWN)],
            'Sim' : '/'
        }
        return { mm1.I_MODEM : props }

    def SetSignalQuality(self, quality):
        self._properties['SignalQuality'] = (
            dbus.types.Struct(
                    [dbus.types.UInt32(quality), True],
                    signature='ub'))

    def SetState(self, state):
        self._properties['State'] = dbus.types.UInt32(state)

    def SetSIM(self, sim):
        self.sim = sim
        if not sim:
            self._properties['Sim'] = '/'
        else:
            self._properties['Sim'] = sim.path

    @dbus.service.method(mm1.I_MODEM, in_signature='b')
    def Enable(self, enable):
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
        raise NotImplementedError()

    @dbus.service.method(mm1.I_MODEM, in_signature='au')
    def SetBands(self, bands):
        raise NotImplementedError()

    @dbus.service.method(mm1.I_MODEM,
                         in_signature='su',
                         out_signature='s')
    def Command(self, cmd, timeout):
        raise NotImplementedError()

    @dbus.service.signal(mm1.I_MODEM, signature='iiu')
    def StateChanged(self, old, new, reason):
        raise NotImplementedError()
