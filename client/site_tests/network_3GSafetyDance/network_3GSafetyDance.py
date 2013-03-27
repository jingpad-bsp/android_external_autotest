# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import backchannel

import logging, re, socket, string, time, urllib2
import dbus, dbus.mainloop.glib, gobject
import random

from autotest_lib.client.cros.cellular.pseudomodem import mm1, pseudomodem, sim

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
        logging.info('Enable')
        self.filterexns(lambda:
            self.flim.EnableTechnology('cellular'))

    def disable(self):
        logging.info('Disable')
        self.filterexns(lambda:
            self.flim.DisableTechnology('cellular'))

    def ignoring(self, status):
        if ('AlreadyConnected' in status['reason'] or
            'Bearer already being connected' in status['reason'] or
            'Bearer already being disconnected' in status['reason'] or
            'InProgress' in status['reason']):
            return True
        if 'NotSupported' in status['reason']:
            # We should only ignore this error if we've previously disabled
            # cellular technology and the service subsequently disappeared
            # when we tried to connect again.
            return not self.flim.FindCellularService(timeout=0)
        return False

    def connect(self):
        logging.info('Connect')
        self.service = self.flim.FindCellularService(timeout=5)
        if self.service:
            (success, status) = self.filterexns(lambda:
                self.flim.ConnectService(service=self.service,
                                         assoc_timeout=120,
                                         config_timeout=120))
            if not success and not self.ignoring(status):
                raise error.TestFail('Could not connect: %s' % status)

    def disconnect(self):
        logging.info('Disconnect')
        self.service = self.flim.FindCellularService(timeout=5)
        if self.service:
            (success, status) = self.filterexns(lambda:
                self.flim.DisconnectService(service=self.service,
                                            wait_timeout=60))
            if not success:
                raise error.TestFail('Could not disconnect: %s' % status)

    def op(self):
        n = random.randint(0, len(self.ops) - 1)
        self.ops[n]()
        time.sleep(random.randint(5, 20) / 10.0)

    def run_once_internal(self, ops=30, seed=None):
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
        self.device = self.flim.FindCellularDevice()
        if not self.device:
            raise error.TestFail('Could not find cellular device.')

        # Ensure that auto connect is turned off so that flimflam does
        # not interfere with running the test
        self.enable()
        service = self.flim.FindCellularService(timeout=30)
        if not service:
            raise error.TestFail('Could not find cellular service')

        props = service.GetProperties()
        favorite = props['Favorite']
        autoconnect = props['AutoConnect']
        logging.info('Favorite = %s, AutoConnect = %s' %
                     (favorite, autoconnect))

        if not favorite:
            logging.info('Enabling Favorite by connecting to service.')
            self.enable()
            self.connect()

            props = service.GetProperties()
            favorite = props['Favorite']
            autoconnect = props['AutoConnect']
            logging.info('Favorite = %s, AutoConnect = %s' %
                         (favorite, autoconnect))

        had_autoconnect = autoconnect

        if autoconnect:
            logging.info('Disabling AutoConnect.')
            service.SetProperty('AutoConnect', dbus.Boolean(0))

            props = service.GetProperties()
            favorite = props['Favorite']
            autoconnect = props['AutoConnect']
            logging.info('Favorite = %s, AutoConnect = %s' %
                         (favorite, autoconnect))

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
                    logging.info('Re-enabling AutoConnect.')
                    service.SetProperty("AutoConnect", dbus.Boolean(1))

    def run_once(self, ops=30, seed=None, pseudo_modem=False):
        # Use a backchannel so that flimflam will restart when the
        # test is over.  This ensures flimflam is in a known good
        # state even if this test fails.
        with backchannel.Backchannel():
            fake_sim = sim.SIM(
                sim.SIM.Carrier('att'),
                mm1.MM_MODEM_ACCESS_TECHNOLOGY_GSM)
            with pseudomodem.TestModemManagerContext(pseudo_modem,
                                                     ['cromo', 'modemmanager'],
                                                     fake_sim):
                self.run_once_internal(ops, seed)
