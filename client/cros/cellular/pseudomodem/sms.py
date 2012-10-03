# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import dbus
import dbus_std_ifaces
import mm1

class SMS(dbus_std_ifaces.DBusProperties):
    """
    Pseudomodem implementation of the org.freedesktop.ModemManager1.Sms
    interface.

    The SMS interface defines operations and properties of a single SMS
    message.

    Modems implementing the Messaging interface will export one SMS object for
    each SMS stored in the device.

    """

    def _InitializeProperties(self):
        raise NotImplementedError()

    @dbus.service.method(mm1.I_SMS)
    def Send(self):
        """
        If the message has not yet been sent, queue it for delivery.

        """
        raise NotImplementedError()

    @dbus.service.method(mm1.I_SMS)
    def Store(self):
        """
        Stores the message in the device if not already done.

        """
        raise NotImplementedError()
