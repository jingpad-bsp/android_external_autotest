# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

import dbus

from autotest_lib.client.cros import flimflam_test_path
import flimflam, mm

class network_ConnmanPowerStateTracking(test.test):
    version = 1

    def cm_state(self):
        status = self.cm_device.GetProperties()
        return status['Powered']

    def mm_state(self):
        status = self.mm.GetAll(self.mm.MODEM_INTERFACE, self.mm_devpath)
        return status['Enabled']

    def mm_enable(self):
        self.modem.Enable(True)

    def mm_disable(self):
        self.modem.Enable(False)

    def require_matching_states(self, when):
        cm_state = self.cm_state()
        mm_state = self.mm_state()
        if cm_state != mm_state and not self.failed:
            self.failed = '%s: cm %s != mm %s' % (when, cm_state, mm_state)

    def run_once(self, name='usb'):
        self.failed = None
        flim = flimflam.FlimFlam(dbus.SystemBus())
        self.cm_device = flim.FindElementByNameSubstring('Device', name)
        if self.cm_device is None:
            self.cm_device = flim.FindElementByPropertySubstring('Device',
                                                                 'Interface',
                                                                 name)
        mm_dev = mm.PickOneModem('')
        self.mm = mm_dev[0]
        self.mm_devpath = mm_dev[1]
        self.modem = self.mm.Modem(self.mm_devpath)
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
        if self.failed:
            raise error.TestFail(self.failed)
