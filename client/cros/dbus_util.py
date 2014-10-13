# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import logging


def dbus2primitive(value):
    """Convert values from dbus types to python types.

    @param value: dbus object to convert to a primitive.

    """
    if isinstance(value, dbus.Boolean):
        return bool(value)
    elif isinstance(value, int):
        return int(value)
    elif isinstance(value, dbus.UInt16):
        return long(value)
    elif isinstance(value, dbus.UInt32):
        return long(value)
    elif isinstance(value, dbus.UInt64):
        return long(value)
    elif isinstance(value, float):
        return float(value)
    elif isinstance(value, str):
        return str(value)
    elif isinstance(value, unicode):
        return str(value)
    elif isinstance(value, list):
        return [dbus2primitive(x) for x in value]
    elif isinstance(value, tuple):
        return tuple([dbus2primitive(x) for x in value])
    elif isinstance(value, dict):
        return dict([(dbus2primitive(k), dbus2primitive(v))
                     for k,v in value.items()])
    else:
        logging.error('Failed to convert dbus object of class: %r',
                      value.__class__.__name__)
        return value
