# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.server import test


class adb_Reboot(test.test):
    """Reboot a device. Should be ran on ADBHosts only."""
    version = 1


    def run_once(self, host):
        if not host.reboot():
            raise error.TestFail('ADB failed to reboot as expected.')
