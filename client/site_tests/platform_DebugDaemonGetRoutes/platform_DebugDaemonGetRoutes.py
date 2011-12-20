# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class platform_DebugDaemonGetRoutes(test.test):
    version = 1

    def run_once(self, *args, **kwargs):
        bus = dbus.SystemBus()
        proxy = bus.get_object('org.chromium.debugd', '/org/chromium/debugd')
        self.iface = dbus.Interface(proxy,
                                    dbus_interface='org.chromium.debugd')
        routes = self.iface.GetRoutes({})
        print 'Routes: %s' % routes
        if 'Kernel IP routing table' not in routes:
            raise error.TestFail("Expected header missing.")
