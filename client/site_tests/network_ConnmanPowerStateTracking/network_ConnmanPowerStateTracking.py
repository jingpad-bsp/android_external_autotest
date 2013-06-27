# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

import dbus

from autotest_lib.client.cros import flimflam_test_path, network
from autotest_lib.client.cros.cellular import mm
import flimflam

class network_ConnmanPowerStateTracking(test.test):
    version = 1

    def cm_state(self):
        status = self.cm_device.GetProperties()
        return status['Powered']

    def mm_state(self):
        properties = self.modem.GetModemProperties()
        return properties['Enabled']

    def mm_enable(self):
        self.modem.Enable(True)

    def mm_disable(self):
        self.modem.Enable(False)

    def require_matching_states(self, when):
        utils.poll_for_condition(
            lambda: self.cm_state() == self.mm_state(),
            exception=
                utils.TimeoutError('Timed out waiting for state convergence'),
            timeout=30)

    def run_once(self):
        flim = flimflam.FlimFlam(dbus.SystemBus())
        network.ResetAllModems(flim)
        self.cm_device = flim.FindCellularDevice()
        manager, modem_path = mm.PickOneModem('')
        self.modem = manager.GetModem(modem_path)
        self.require_matching_states('Before')
        if self.mm_state() == 1:
            self.mm_disable()
            self.require_matching_states('During')
            self.mm_enable()
        else:
            self.mm_enable()
            self.require_matching_states('During')
            self.mm_disable()
        self.require_matching_states('After')
