# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import dbus_std_ifaces
import mm1

class Bearer(dbus_std_ifaces.DBusProperties):
    """
    Fake implementation of the org.freedesktop.ModemManager1.Bearer
    interface. Bearer objects are owned and managed by specific Modem objects.
    A single Modem may expose one or more Bearer objects, which can then be
    used to get the modem into connected state.

    """

    def _InitializeProperties(self):
        raise NotImplementedError()

    @dbus.service.method(mm1.I_BEARER)
    def Connect(self):
        """
        Requests activation of a packet data connection with the network using
        this bearer's properties. Upon successful activation, the modem can
        send and receive packet data and, depending on the addressing
        capability of the modem, a connection manager may need to start PPP,
        perform DHCP, or assign the IP address returned by the modem to the
        data interface. Upon successful return, the "Ip4Config" and/or
        "Ip6Config" properties become valid and may contain IP configuration
        information for the data interface associated with this bearer.

        Since this is a mock implementation, this bearer will not establish
        a real connection with the outside world. Since shill does not specify
        IP addressing information to the bearer, we do not need to populate
        these properties.

        """
        raise NotImplementedError()

    @dbus.service.method(mm1.I_BEARER)
    def Disconnect(self):
        """
        Disconnect and deactivate this packet data connection. In a real bearer,
        any ongoing data session would be terminated and IP addresses would
        become invalid when this method is called, however, the fake
        implementation doesn't set the IP properties.

        """
        raise NotImplementedError()
