# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

import os, time
import dbus, dbus.mainloop.glib, gobject
import random

from autotest_lib.client.cros import flimflam_test_path
import mm

class TestFailure(Exception):
    pass

class network_LockedSIM(test.test):
    version = 1

    def modem(self, mm):
        return self.bus.get_object(mm[0].service, mm[1])

    def EnableModem(self, mm):
        self.modem(mm).Enable(True, dbus_interface=self.imodem)

    def ChangePin(self, mm, old, new):
        self.modem(mm).ChangePin(old, new, dbus_interface=self.icard)

    def EnablePin(self, mm, pin):
        self.modem(mm).EnablePin(pin, True, dbus_interface=self.icard)

    def DisablePin(self, mm, pin):
        self.modem(mm).EnablePin(pin, False, dbus_interface=self.icard)

    def Reset(self, mm):
        self.modem(mm).Reset(dbus_interface=self.imodem)

    def Unlock(self, mm, pin):
        self.modem(mm).SendPin(pin, dbus_interface=self.icard)

    def retries(self, mm):
        return self.modem(mm).Get(self.imodem, 'UnlockRetries',
                                    dbus_interface=self.iprops)

    def run_once(self):
        global mm
        self.iprops = 'org.freedesktop.DBus.Properties'
        self.imm = 'org.freedesktop.ModemManager'
        self.imodem = 'org.freedesktop.ModemManager.Modem'
        self.icard = 'org.freedesktop.ModemManager.Modem.Gsm.Card'
        failed = []
        self.bus = dbus.SystemBus()

        self.devs = mm.EnumerateDevices()
        print 'devs: %d' % len(self.devs)
        for modem in self.devs:
            print 'device: %s' % modem[1]
            # Make sure we can change the pin - this guarantees that the pin is
            # properly set to start with.
            try:
                self.Unlock(modem, '1111')
            except dbus.exceptions.DBusException:
                # We get this back if the sim's already unlocked.
                pass
            self.EnableModem(modem)
            self.ChangePin(modem, '1111', '1112')
            self.ChangePin(modem, '1112', '1111')
            try:
                self.DisablePin(modem, '1111')
            except dbus.exceptions.DBusException:
                # We get this back if the pin's already disabled.
                pass
            self.EnablePin(modem, '1111')
            self.Reset(modem)

        # Give the modem a little while to come back...
        time.sleep(20)

        # Re-enumerate devices, since we're hoping they all disappeared and
        # reappeared.
        self.devs = mm.EnumerateDevices()
        print 'newdevs: %d' % len(self.devs)
        for modem in self.devs:
            print 'newdevice: %s' % modem[1]
            # Send a command to the modem, then wait a second. It seems to take
            # the Ericsson F3307 (at least) from initial access to usefulness,
            # so we make a dummy retries() call, wait a second, then get the
            # real retry count.
            self.retries(modem)
            time.sleep(1)
            retries = self.retries(modem)
            print 'real retries: %u' % retries
            if retries < 2:
                print 'retries too low (%d), bailing' % retries
                failed.append(modem)
                continue
            try:
                self.Unlock(modem, '1112')
            except dbus.exceptions.DBusException:
                pass
                # We expect a failure here, so swallow the DBus exception.
            nretries = self.retries(modem)
            self.Unlock(modem, '1111')
            self.EnableModem(modem)
            self.DisablePin(modem, '1111')
            print '%s retries %d nretries %d' % (modem, retries, nretries)
            if nretries != (retries - 1):
                # We can't just raise the exception here - if there are multiple
                # modems in the system, we might raise on the first one and
                # leave the others locked.
                failed.append(modem)

        if failed:
            raise error.TestFail("Failed for devices: %s" % ', '.join(
                map(lambda x: x[1], failed)))
