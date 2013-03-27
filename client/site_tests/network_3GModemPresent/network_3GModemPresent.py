# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

import dbus

from autotest_lib.client.cros.cellular.pseudomodem import mm1, pseudomodem, sim
from autotest_lib.client.cros import flimflam_test_path
import flimflam

class network_3GModemPresent(test.test):
    version = 1

    def run_once(self, pseudo_modem=False):
        with pseudomodem.TestModemManagerContext(pseudo_modem,
                                                 ['cromo', 'modemmanager']):
            flim = flimflam.FlimFlam()

            device = flim.FindCellularDevice()
            if not device:
                raise error.TestFail("Could not find cellular device")
