# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

import logging, re, socket, string, time, urllib2
import dbus, dbus.mainloop.glib, gobject
import random

from autotest_lib.client.cros import flimflam_test_path
import flimflam

class network_3GSafetyDance(test.test):
    version = 1

    def filterexns(self, fn):
        v = None
        try:
            v = fn()
        except dbus.exceptions.DBusException, error:
            if error._dbus_error_name in self.okerrors:
                return v
            else:
                raise error
        return v

    def enable(self):
        print 'Enable'
        self.filterexns(lambda:
            self.flim.EnableTechnology('cellular'))

    def disable(self):
        print 'Disable'
        self.filterexns(lambda:
            self.flim.DisableTechnology('cellular'))

    def ignoring(self, status):
        if 'AlreadyConnected' in status['reason']:
            return True
        if 'InProgress' in status['reason']:
            return True
        return False

    def connect(self):
        print 'Connect'
        self.service = self.flim.FindCellularService(timeout=5)
        if self.service:
            (success, status) = self.filterexns(lambda:
                self.flim.ConnectService(service = self.service,
                                         config_timeout = 120))
            if not success and not self.ignoring(status):
                raise error.TestFail('Could not connect: %s' % status)

    def disconnect(self):
        print 'Disconnect'
        self.service = self.flim.FindCellularService(timeout=5)
        if self.service:
            (success, status) = self.filterexns(lambda:
                self.flim.DisconnectService(service = self.service,
                                            wait_timeout = 60))
            if not success:
                raise error.TestFail('Could not disconnect: %s' % status)

    def op(self):
        n = random.randint(0, len(self.ops) - 1)
        self.ops[n]()
        time.sleep(random.randint(5, 20) / 10.0)

    def run_once(self, name='usb', ops=30, seed=None):
        if not seed:
            seed = int(time.time())
        self.okerrors = [
            'org.chromium.flimflam.Error.InProgress',
            'org.chromium.flimflam.Error.AlreadyConnected',
            'org.chromium.flimflam.Error.AlreadyEnabled',
            'org.chromium.flimflam.Error.AlreadyDisabled'
        ]
        self.ops = [ self.enable,
                     self.disable,
                     self.connect,
                     self.disconnect ]
        self.flim = flimflam.FlimFlam()
        self.manager = flimflam.DeviceManager(self.flim)
        self.device = self.flim.FindElementByNameSubstring('Device', name)
        if not self.device:
            self.device = self.flim.FindElementByPropertySubstring('Device',
                                                                   'Interface',
                                                                   name)

        # Ensure that auto connect is turned off so that flimflam does
        # not interfere with running the test
        self.enable()
        service = self.flim.FindCellularService(timeout=5)

        props = service.GetProperties()
        favorite = props['Favorite']
        autoconnect = props['AutoConnect']
        print 'Favorite = %s, AutoConnect = %s' % (favorite, autoconnect)

        if not favorite:
            print 'Enabling Favorite by connecting to service.'
            self.enable()
            self.connect()

            props = service.GetProperties()
            favorite = props['Favorite']
            autoconnect = props['AutoConnect']
            print 'Favorite = %s, AutoConnect = %s' % (favorite, autoconnect)

        had_autoconnect = autoconnect

        if autoconnect:
            print 'Disabling AutoConnect.'
            service.SetProperty('AutoConnect', dbus.Boolean(0))

            props = service.GetProperties()
            favorite = props['Favorite']
            autoconnect = props['AutoConnect']
            print 'Favorite = %s, AutoConnect = %s' % (favorite, autoconnect)

        if not favorite:
            raise error.TestFail('Favorite=False, but we want it to be True')

        if autoconnect:
            raise error.TestFail('AutoConnect=True, but we want it to be False')

        logging.info('Seed: %d' % seed)
        random.seed(seed)
        try:
            for _ in xrange(ops):
                self.op()
        finally:
            # Re-enable auto connect
            self.enable()
            if had_autoconnect:
                service = self.flim.FindCellularService(timeout=5)
                if service:
                    print 'Re-enabling AutoConnect.'
                    service.SetProperty("AutoConnect", dbus.Boolean(1))
