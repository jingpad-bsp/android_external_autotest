# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


BUFFET_SERVICE_NAME = 'org.chromium.Buffet'

BUFFET_MANAGER_INTERFACE = 'org.chromium.Buffet.Manager'
BUFFET_MANAGER_OBJECT_PATH = '/org/chromium/Buffet/Manager'

TEST_STATE_KEY = 'test_state_key'
TEST_STATE_VALUE = 'test_state_value'

class buffet_BasicDBusAPI(test.test):
    """Check that basic buffet daemon DBus APIs are functional."""
    version = 1

    def run_once(self):
        """Test entry point."""
        bus = dbus.SystemBus()
        manager_proxy = bus.get_object(
                BUFFET_SERVICE_NAME, BUFFET_MANAGER_OBJECT_PATH)
        test_message = 'Hello world!'
        echoed_message = manager_proxy.TestMethod(
                test_message, dbus_interface=BUFFET_MANAGER_INTERFACE)
        if test_message != echoed_message:
            raise error.TestFail('Expected Manager.TestMethod to return %s '
                                 'but got %s instead.' % (test_message,
                                                          echoed_message))
