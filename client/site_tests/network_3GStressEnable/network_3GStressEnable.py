# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

import logging, re, socket, string, time, urllib2
import dbus, dbus.mainloop.glib, gobject

from autotest_lib.client.cros import flimflam_test_path
import flimflam, mm

class network_3GStressEnable(test.test):
    version = 1

    okerrors = [
        'org.chromium.flimflam.Error.InProgress'
    ]

    def SetPowered(self, device, state):
        try:
            device.SetProperty('Powered', dbus.Boolean(state))
        except dbus.exceptions.DBusException, error:
            if error._dbus_error_name in network_3GStressEnable.okerrors:
                return
            else:
                raise error

    def test(self, device, settle):
        self.SetPowered(device, 1)
        time.sleep(settle)
        self.SetPowered(device, 0)
        time.sleep(settle)

    def run_once(self, name='usb', cycles=3, min=5, max=15):
        flim = flimflam.FlimFlam(dbus.SystemBus())
        device = flim.FindElementByNameSubstring('Device', name)
        if device is None:
            device = flim.FindElementByPropertySubstring('Device', 'Interface',
                                                         name)
        service = flim.FindElementByNameSubstring('Service', 'cellular')
        if service:
            # If cellular's already up, take it down to start.
	    service.SetProperty('AutoConnect', False)
	    self.SetPowered(device, 0)
        for t in xrange(max, min, -1):
            for _ in xrange(cycles):
                self.test(device, t / 10.0)
