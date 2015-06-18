# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus

from autotest_lib.client.cros import dbus_util

MANAGER_INTERFACE = 'org.chromium.Buffet.Manager'

class BuffetDBusHelper(object):
    """Delegate representing an instance of buffet."""

    def __init__(self):
        """Construct a BuffetDBusHelper.

        You should probably use get_helper() above rather than call this
        directly.

        @param manager_proxy: DBus proxy for the Manager object.

        """
        bus = dbus.SystemBus()
        manager_proxy = bus.get_object('org.chromium.Buffet',
                                       '/org/chromium/Buffet/Manager')
        self.manager = dbus.Interface(manager_proxy, MANAGER_INTERFACE)
        self.properties = dbus.Interface(manager_proxy,
                                         'org.freedesktop.DBus.Properties')

    def __getattr__(self, name):
        components = name.split('_')
        name = ''.join(x.title() for x in components)
        dbus_value = self.properties.Get(MANAGER_INTERFACE, name)
        return dbus_util.dbus2primitive(dbus_value)
