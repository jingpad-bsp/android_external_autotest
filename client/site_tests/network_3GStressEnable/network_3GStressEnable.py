# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import backchannel

import logging, re, socket, string, time, urllib2
import dbus, dbus.mainloop.glib, gobject

from autotest_lib.client.cros import flimflam_test_path
import flimflam, mm
from autotest_lib.client.cros.cellular.pseudomodem import mm1, pseudomodem, sim

class network_3GStressEnable(test.test):
    version = 1

    okerrors = [
        'org.chromium.flimflam.Error.InProgress'
    ]

    def EnableDevice(self, enable):
        try:
            if enable:
                self.device.Enable()
            else:
                self.device.Disable()
        except dbus.exceptions.DBusException, err:
            if err._dbus_error_name in network_3GStressEnable.okerrors:
                return
            else:
                raise error.TestFail(err)

    def test(self, settle):
        self.EnableDevice(True)
        time.sleep(settle)
        self.EnableDevice(False)
        time.sleep(settle)

    def run_once_internal(self, cycles, min, max):
        self.flim = flimflam.FlimFlam(dbus.SystemBus())
        self.device = self.flim.FindCellularDevice()
        if not self.device:
            raise error.TestFail('Failed to find a cellular device.')
        service = self.flim.FindCellularService()
        if service:
            # If cellular's already up, take it down to start.
            try:
                service.SetProperty('AutoConnect', False)
            except dbus.exceptions.DBusException, err:
                # If the device has never connected to the cellular service
                # before, flimflam will raise InvalidService when attempting
                # to change the AutoConnect property.
                if err._dbus_error_name != 'org.chromium.flimflam.'\
                                             'Error.InvalidService':
                    raise err
            self.EnableDevice(False)
        for t in xrange(max, min, -1):
            for n in xrange(cycles):
                # deciseconds are an awesome unit.
                print 'Cycle %d: %f seconds delay.' % (n, t / 10.0)
                self.test(t / 10.0)
        print 'Done.'

    def run_once(self, cycles=3, min=15, max=25, use_pseudomodem=False):
        with backchannel.Backchannel():
            fake_sim = sim.SIM(sim.SIM.Carrier('att'),
                mm1.MM_MODEM_ACCESS_TECHNOLOGY_GSM)
            with pseudomodem.TestModemManagerContext(use_pseudomodem,
                                                     sim=fake_sim):
                self.run_once_internal(cycles, min, max)
