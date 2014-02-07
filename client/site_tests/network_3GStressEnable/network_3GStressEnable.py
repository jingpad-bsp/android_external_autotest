# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import backchannel
from autotest_lib.client.cros import network
from autotest_lib.client.cros.cellular.pseudomodem import pseudomodem_context

import time
import dbus

from autotest_lib.client.cros import flimflam_test_path
import flimflam

DEVICE_TIMEOUT=45

class network_3GStressEnable(test.test):
    """
    Stress-tests enabling and disabling a technology at short intervals.

    """
    version = 1

    okerrors = [
        'org.chromium.flimflam.Error.InProgress'
    ]

    def _enable_device(self, enable):
        try:
            if enable:
                self.device.Enable(timeout=DEVICE_TIMEOUT)
            else:
                self.device.Disable(timeout=DEVICE_TIMEOUT)
        except dbus.exceptions.DBusException, err:
            if err._dbus_error_name in network_3GStressEnable.okerrors:
                return
            else:
                raise error.TestFail(err)

    def _test(self, settle):
        self._enable_device(True)
        time.sleep(settle)
        self._enable_device(False)
        time.sleep(settle)

    def _run_once_internal(self, cycles, min, max):
        self.flim = flimflam.FlimFlam(dbus.SystemBus())
        network.ResetAllModems(self.flim)
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
            self._enable_device(False)
        for t in xrange(max, min, -1):
            for n in xrange(cycles):
                # deciseconds are an awesome unit.
                print 'Cycle %d: %f seconds delay.' % (n, t / 10.0)
                self._test(t / 10.0)
        print 'Done.'

    def run_once(self, cycles=3, min=15, max=25, use_pseudomodem=False,
                 pseudomodem_family='3GPP'):
        with backchannel.Backchannel():
            with pseudomodem_context.PseudoModemManagerContext(
                    use_pseudomodem,
                    {'family' : pseudomodem_family}):
                self._run_once_internal(cycles, min, max)
