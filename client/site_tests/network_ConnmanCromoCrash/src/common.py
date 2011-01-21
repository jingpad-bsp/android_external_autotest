# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus, glib, gobject

from autotest_lib.client.cros import cros_flimflam
import flimflam_test

Modem = flimflam_test.Modem
ModemManager = flimflam_test.ModemManager
OCMM = flimflam_test.OCMM

class RandomError(RuntimeError):
    pass

def cleanup(fn):
    glib.timeout_add_seconds(5, fn)

def setup(fn=None):
    global bus
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    if fn:
        glib.timeout_add_seconds(1, fn)

def run():
    mainloop = gobject.MainLoop()
    print "Running test modemmanager."
    name = dbus.service.BusName(flimflam_test.CMM, bus)
    mainloop.run()

