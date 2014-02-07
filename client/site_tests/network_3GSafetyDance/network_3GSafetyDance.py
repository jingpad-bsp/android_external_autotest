# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import logging
import random
import time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import backchannel
from autotest_lib.client.cros.cellular import cell_tools
from autotest_lib.client.cros.cellular.pseudomodem import pseudomodem_context

from autotest_lib.client.cros import flimflam_test_path
import flimflam

class network_3GSafetyDance(test.test):
    """
    Stress tests all connection manager 3G operations.

    This test runs a long series of 3G operations in pseudorandom order. All of
    these 3G operations must return a convincing result (EINPROGRESS or no
    error).

    """
    version = 1

    def _filterexns(self, fn):
        v = None
        try:
            v = fn()
        except dbus.exceptions.DBusException, error:
            if error._dbus_error_name in self.okerrors:
                return v
            else:
                raise error
        return v

    def _enable(self):
        logging.info('Enable')
        self._filterexns(lambda:
            self.flim.EnableTechnology('cellular'))

    def _disable(self):
        logging.info('Disable')
        self._filterexns(lambda:
            self.flim.DisableTechnology('cellular'))

    def _ignoring(self, status):
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

    def _connect(self):
        logging.info('Connect')
        self.service = self.flim.FindCellularService(timeout=5)
        if self.service:
            (success, status) = self._filterexns(lambda:
                self.flim.ConnectService(service=self.service,
                                         assoc_timeout=120,
                                         config_timeout=120))
            if not success and not self._ignoring(status):
                raise error.TestFail('Could not connect: %s' % status)

    def _disconnect(self):
        logging.info('Disconnect')
        self.service = self.flim.FindCellularService(timeout=5)
        if self.service:
            (success, status) = self._filterexns(lambda:
                self.flim.DisconnectService(service=self.service,
                                            wait_timeout=60))
            if not success:
                raise error.TestFail('Could not disconnect: %s' % status)

    def _op(self):
        n = random.randint(0, len(self.ops) - 1)
        self.ops[n]()
        time.sleep(random.randint(5, 20) / 10.0)

    def _run_once_internal(self, ops=30, seed=None):
        if not seed:
            seed = int(time.time())
        self.okerrors = [
            'org.chromium.flimflam.Error.InProgress',
            'org.chromium.flimflam.Error.AlreadyConnected',
            'org.chromium.flimflam.Error.AlreadyEnabled',
            'org.chromium.flimflam.Error.AlreadyDisabled'
        ]
        self.ops = [ self._enable,
                     self._disable,
                     self._connect,
                     self._disconnect ]
        self.flim = flimflam.FlimFlam()
        self.manager = flimflam.DeviceManager(self.flim)
        self.device = self.flim.FindCellularDevice()
        if not self.device:
            raise error.TestFail('Could not find cellular device.')

        self.flim.SetDebugTags(
                'dbus+service+device+modem+cellular+portal+network+'
                'manager+dhcp')

        # Ensure that auto connect is turned off so that flimflam does
        # not interfere with running the test
        with cell_tools.AutoConnectContext(self.device, self.flim, False):
            # Start in a known state.
            self._disable()
            logging.info('Seed: %d', seed)
            random.seed(seed)
            for _ in xrange(ops):
                self._op()

    def run_once(self, ops=30, seed=None,
                 pseudo_modem=False,
                 pseudomodem_family='3GPP'):
        # Use a backchannel so that flimflam will restart when the
        # test is over.  This ensures flimflam is in a known good
        # state even if this test fails.
        with backchannel.Backchannel():
            with pseudomodem_context.PseudoModemManagerContext(
                    pseudo_modem,
                    {'family' : pseudomodem_family}):
                self._run_once_internal(ops, seed)
