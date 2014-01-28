# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.cellular.pseudomodem import pseudomodem_context

from autotest_lib.client.cros import flimflam_test_path
import flimflam

class network_3GModemPresent(test.test):
    """
    Tests that a 3G modem is available.

    The test attempts to find a shill device corresponding to a cellular modem.

    """
    version = 1

    def run_once(self, pseudo_modem=False, pseudomodem_family='3GPP'):
        with pseudomodem_context.PseudoModemManagerContext(
                pseudo_modem,
                {'family': pseudomodem_family}):
            flim = flimflam.FlimFlam()
            device = flim.FindCellularDevice()
            if not device:
                raise error.TestFail("Could not find cellular device")
