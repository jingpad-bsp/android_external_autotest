# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

import dbus

class platform_CrosDisksDBus(test.test):
    version = 1

    def run_once(self):
        # TODO(rtc): Excercise the whole API.
        bus = dbus.SystemBus()
        proxy = bus.get_object('org.chromium.CrosDisks',
                               '/org/chromium/CrosDisks')
        cros_disks = dbus.Interface(proxy, 'org.chromium.CrosDisks')
        is_alive = cros_disks.IsAlive()
        if not is_alive:
            raise error.TestFail("Unable to talk to the disk daemon")
