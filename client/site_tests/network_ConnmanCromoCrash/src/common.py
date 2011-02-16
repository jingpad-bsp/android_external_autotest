# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus, glib, gobject, os, sys

sys.path.append(os.environ.get("SYSROOT", "/usr/local/") + "lib/flimflam/test")

import flimflam_test

Modem = flimflam_test.Modem
ModemManager = flimflam_test.ModemManager
OCMM = flimflam_test.OCMM

name = None

class RandomError(RuntimeError):
    pass

def cleanup(fn, after=5):
    glib.timeout_add_seconds(after, fn)

def setup(fn=None):
    global bus, name
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    name = dbus.service.BusName(flimflam_test.CMM, bus)
    if fn:
        glib.timeout_add_seconds(1, fn)

def run():
    mainloop = gobject.MainLoop()
    print "Running test modemmanager."
    mainloop.run()

