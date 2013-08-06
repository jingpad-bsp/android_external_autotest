# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import dbus_std_ifaces
import mm1

class Testing(dbus_std_ifaces.DBusProperties):
    """
    The testing object allows the pseudomodem to be configured on the fly
    over D-Bus. It exposes a basic set of commands that can be used to
    simulate network events (such as SMS) or various other modem configurations
    that are needed for testing/debugging.

    """

    def __init__(self, modem, bus):
        self._modem = modem
        dbus_std_ifaces.DBusProperties.__init__(self, mm1.TESTING_PATH, bus)

    def _InitializeProperties(self):
        return { mm1.I_TESTING: { 'Modem': self._modem.path } }

    @dbus.service.method(mm1.I_TESTING, in_signature='a{sv}')
    def ReceiveSms(self, properties):
        """
        Simulates a fake SMS.

        @param properties: Dictionary, containing the SMS properties, as
                defined according to org.freedesktop.ModemManager1.Sms.

        """
        raise NotImplementedError()
