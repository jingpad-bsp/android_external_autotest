#!/usr/bin/python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common DBus Setup"""

import dbus
import dbus.mainloop.glib
import warnings

# Disable DBus deprecation warnings.
# TODO: Remove when we upgrade to a newer dbus-python.
warnings.filterwarnings(action='ignore', category=DeprecationWarning,
                        module=r'.*dbus.*')

FLIMFLAM = 'org.chromium.flimflam'

bus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus(mainloop=bus_loop)
manager = dbus.Interface(bus.get_object(FLIMFLAM, '/'), FLIMFLAM + '.Manager')
