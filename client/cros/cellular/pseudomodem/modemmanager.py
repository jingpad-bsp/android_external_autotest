# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import dbus_std_ifaces
import mm1

LOG_LEVELS = ['ERR', 'WARN', 'INFO', 'DEBUG']

class ModemManager(dbus_std_ifaces.DBusObjectManager):
    """
    Pseudomodem implementation of org.freedesktop.ModemManager1

    """
    def __init__(self, bus):
        dbus_std_ifaces.DBusObjectManager.__init__(self, bus, mm1.MM1)
        self.debug_level = 'INFO'

    @dbus.service.method(mm1.I_MODEM_MANAGER)
    def ScanDevices(self):
        """
        Starts a new scan for connected modem devices.

        """
        # TODO(armansito): For now this method is a noop. shill
        # doesn't use this method afaik, but it doesn't make sense
        # for a fake modem to do anything here anyway. Perhaps
        # we can give the pseudo modem manager a list of fake
        # modems upon initialization, and this method would add them?
        pass

    @dbus.service.method(mm1.I_MODEM_MANAGER, in_signature='s')
    def SetLogging(self, level):
        """
        Sets logging verbosity.

        @param level: One of "ERR", "WARN", "INFO", "DEBUG"

        """
        if level not in LOG_LEVELS:
            raise mm1.MMCoreError(
                mm1.MMCoreError.INVALID_ARGS)
