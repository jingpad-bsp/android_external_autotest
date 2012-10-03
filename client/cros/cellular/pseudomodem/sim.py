# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import dbus
import dbus_std_ifaces
import mm1

class SIM(dbus_std_ifaces.DBusProperties):
    """
    Pseudomodem implementation of the org.freedesktop.ModemManager1.Sim
    interface.

    Broadband modems usually need a SIM card to operate. Each Modem object will
    therefore expose up to one SIM object, which allows SIM-specific actions
    such as PIN unlocking.

    The SIM interface handles communication with SIM, USIM, and RUIM (CDMA SIM)
    cards.

    """

    def _InitializeProperties(self):
        raise NotImplementedError()

    @dbus.service.method(mm1.I_SIM, in_signature='s')
    def SendPin(self, pin):
        """
        Sends the PIN to unlock the SIM card.

        Args:
            pin -- A string containing the PIN code.

        """
        raise NotImplementedError()

    @dbus.service.method(mm1.I_SIM, in_signature='ss')
    def SendPuk(self, puk, pin):
        """
        Sends the PUK and a new PIN to unlock the SIM card.

        Args:
            puk -- A string containing the PUK code.
            pin -- A string containing the PIN code.

        """
        raise NotImplementedError()

    @dbus.service.method(mm1.I_SIM, in_signature='sb')
    def EnablePin(self, pin, enabled):
        """
        Enables or disables PIN checking.

        Args:
            pin -- A string containing the PIN code.
            enabled -- TRUE to enable PIN, FALSE otherwise.

        """
        raise NotImplementedError()

    @dbus.service.method(mm1.I_SIM, in_signature='ss')
    def ChangePin(self, old_pin, new_pin):
        """
        Changes the PIN code.

        Args:
            old_pin -- A string containing the old PIN code.
            new_pin -- A string containing the new PIN code.

        """
        raise NotImplementedError()
