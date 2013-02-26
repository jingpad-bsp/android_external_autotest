# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import logging

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


class platform_DebugDaemonGetPerfData(test.test):
    version = 1


    def run_once(self, *args, **kwargs):
        bus = dbus.SystemBus()
        proxy = bus.get_object('org.chromium.debugd', '/org/chromium/debugd')
        self.iface = dbus.Interface(proxy,
                                    dbus_interface='org.chromium.debugd')
        profile_duration_seconds = 2
        result = self.iface.GetPerfData(profile_duration_seconds)
        logging.info('Result: %s', result)
        if not result:
            raise error.TestFail('No perf output found: %s' % result)
        if len(result) < 10:
            raise error.TestFail('Perf output too small')
