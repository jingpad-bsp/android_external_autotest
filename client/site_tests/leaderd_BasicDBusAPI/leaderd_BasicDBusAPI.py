# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


SERVICE_NAME = 'org.chromium.leaderd'
MANAGER_INTERFACE = 'org.chromium.leaderd.Manager'
MANAGER_OBJECT_PATH = '/org/chromium/leaderd/Manager'

EXPECTED_PING_RESPONSE = 'Hello world!'

class leaderd_BasicDBusAPI(test.test):
    """Check that basic leaderd daemon DBus APIs are functional."""
    version = 1

    def run_once(self):
        """Test entry point."""
        bus = dbus.SystemBus()
        manager_proxy = dbus.Interface(
                bus.get_object(SERVICE_NAME, MANAGER_OBJECT_PATH),
                dbus_interface=MANAGER_INTERFACE)
        ping_response = manager_proxy.Ping()
        if EXPECTED_PING_RESPONSE != ping_response:
            raise error.TestFail(
                    'Expected Manager.Ping to return %s but got %s instead.' %
                    (EXPECTED_PING_RESPONSE, ping_response))
