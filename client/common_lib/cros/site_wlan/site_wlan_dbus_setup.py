#!/usr/bin/python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common DBus Setup"""

import dbus
import dbus.mainloop.glib
import warnings

# Once these are no longer copied to DUTs manually, this should become
# from autotest_lib.client.common_lib.cros.site_wlan import constants
import constants

# Disable DBus deprecation warnings.
# TODO: Remove when we upgrade to a newer dbus-python.
warnings.filterwarnings(action='ignore', category=DeprecationWarning,
                        module=r'.*dbus.*')

bus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus(mainloop=bus_loop)
manager = dbus.Interface(bus.get_object(constants.CONNECTION_MANAGER, '/'),
                         constants.CONNECTION_MANAGER_MANAGER)


def GetObject(kind, path):
  """Returns a DBus interface for the specified object.

  Args:
    kind: String containing the type of object such as "Profile" or "Service".
    path: String containing the DBus path to the object.

  Returns:
    The DBus interface to the object.
  """
  return dbus.Interface(bus.get_object(constants.CONNECTION_MANAGER, path),
                        '.'.join([constants.CONNECTION_MANAGER, kind]))


def GetObjectList(kind, path_list):
  if not path_list:
    path_list = manager.GetProperties().get(kind + 's', [])
  return [GetObject(kind, path) for path in path_list]
