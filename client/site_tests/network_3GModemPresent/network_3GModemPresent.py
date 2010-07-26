# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

import dbus, os, sys

import_path = os.environ.get("SYSROOT", "") + "/usr/lib/flimflam/test"
sys.path.append(import_path)
import flimflam

class network_3GModemPresent(test.test):
    version = 1

    def run_once(self):
        flim = flimflam.FlimFlam()

        device = flim.FindElementByPropertySubstring("Device",
                                                     "Type",
                                                     "cellular")
        if not device:
            raise error.TestFail("Could not find cellular device")
