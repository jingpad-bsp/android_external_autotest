# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import dbus.service
import mm1

# TODO(armansito): Have this class implement all Messaging methods
# and make Modems have a reference to an instance of Messaging
# OR have Modem implement this

class Messaging(dbus.service.Interface):
    """
    Python binding for the org.freedesktop.ModemManager1.Modem.Messaging
    interface. The Messaging interfaces handles sending SMS messages and
    notification of new incoming messages.

    """

    @dbus.service.method(mm1.I_MODEM_MESSAGING, out_signature='ao')
    def List(self):
        """
        Retrieves all SMS messages.
        This method should only be used once and subsequent information
        retrieved either by listening for the "Added" and "Completed" signals,
        or by querying the specific SMS object of interest.

        Returns:
            The list of SMS object paths.

        Emits:
            Added
            Completed

        """
        raise NotImplementedError()

    @dbus.service.method(mm1.I_MODEM_MESSAGING, in_signature='o')
    def Delete(self, path):
        """
        Deletes an SMS message.

        Args:
            The object path of the SMS to delete.

        Emits:
            Deleted

        """
        raise NotImplementedError()

    @dbus.service.method(mm1.I_MODEM_MESSAGING,
                         in_signature='a{sv}',
                         out_signature='o')
    def Create(self, properties):
        """
        Creates a new message object. The 'Number' and 'Text' properties are
        mandatory, others are optional. If the SMSC is not specified and one is
        required, the default SMSC is used.

        Args:
            properties -- Message properties from the SMS D-Bus interface.

        Returns:
            The object path of the new message object.

        """
        raise NotImplementedError()

    @dbus.service.signal(mm1.I_MODEM_MESSAGING, signature='ob')
    def Added(self, path, received):
        raise NotImplementedError()

    @dbus.service.signal(mm1.I_MODEM_MESSAGING, signature='o')
    def Completed(self, path):
        raise NotImplementedError()

    @dbus.service.signal(mm1.I_MODEM_MESSAGING, signature='o')
    def Deleted(self, path):
        raise NotImplementedError()
