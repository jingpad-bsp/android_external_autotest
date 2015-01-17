# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


PRIVETD_SERVICE_NAME = 'org.chromium.privetd'

PRIVETD_MANAGER_INTERFACE = 'org.chromium.privetd.Manager'
PRIVETD_MANAGER_OBJECT_PATH = '/org/chromium/privetd/Manager'

class privetd_BasicDBusAPI(test.test):
    """Check that basic privetd daemon DBus APIs are functional."""
    version = 1

    def run_once(self):
        """Test entry point."""
        bus = dbus.SystemBus()
        manager_proxy = bus.get_object(
                PRIVETD_SERVICE_NAME, PRIVETD_MANAGER_OBJECT_PATH)
        test_message = 'Hello world!'
        echoed_message = manager_proxy.Ping(
                dbus_interface=PRIVETD_MANAGER_INTERFACE)
        if test_message != echoed_message:
            raise error.TestFail('Expected Manager.Ping to return %s '
                                 'but got %s instead.' % (test_message,
                                                          echoed_message))
