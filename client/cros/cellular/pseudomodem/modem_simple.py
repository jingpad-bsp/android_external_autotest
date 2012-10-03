# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import dbus.service
import mm1


class ModemSimple(dbus.service.Object):
    """
    Python binding for the org.freedesktop.ModemManager1.Modem.Simple
    interface. All subclasses of Modem must implement this interface.
    The Simple interface allows controlling and querying the status of
    modems.

    """

    @dbus.service.method(mm1.I_MODEM_SIMPLE,
                         in_signature='a{sv}',
                         out_signature='o')
    def Connect(self, properties):
    """
    Do everything needed to connect the modem using the given properties.

    This method will attempt to find a matching packet data bearer and activate
    it if necessary, returning the bearer's IP details. If no matching bearer is
    found, a new bearer will be created and activated, but this operation may
    fail if no resources are available to complete this connection attempt
    (i.e., if a conflicting bearer is already active).

    This call may make a large number of changes to modem configuration based
    on properties passed in. For example, given a PIN-locked, disabled GSM/UMTS
    modem, this call may unlock the SIM PIN, alter the access technology
    preference, wait for network registration (or force registration to a
    specific provider), create a new packet data bearer using the given "apn",
    and connect that bearer.

    Args:
        properties -- See the ModemManager Reference Manual for the allowed
                      key/value pairs in properties.

    Returns:
        On successfult connect, returns the object path of the connected packet
        data bearer used for the connection attempt.

    """
        raise NotImplementedError()

    @dbus.service.method(mm1.I_MODEM_SIMPLE, in_signature='o')
    def Disconnect(self, bearer):
    """
    Disconnect an active packet data connection.

    Args:
        bearer -- The object path of the data bearer to disconnect. If the path
                  is "/" (i.e. no object given) this method will disconnect all
                  active packet data bearers.

    """
        raise NotImplementedError()

    @dbus.service.method(mm1.I_MODEM_SIMPLE, out_signature='a{sv}')
    def GetStatus(self):
    """
    Gets the general modem status.

    Returns:
        Dictionary of properties. See the ModemManager Reference Manual
        for the predefined common properties.

    """
        raise NotImplementedError()
