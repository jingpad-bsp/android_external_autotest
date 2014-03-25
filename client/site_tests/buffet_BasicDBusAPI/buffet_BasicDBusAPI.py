# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import logging

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


BUFFET_SERVICE_NAME = 'org.chromium.Buffet'

BUFFET_ROOT_INTERFACE = 'org.chromium.Buffet'
BUFFET_ROOT_OBJECT_PATH = '/org/chromium/Buffet'

BUFFET_MANAGER_INTERFACE = 'org.chromium.Buffet.Manager'
BUFFET_MANAGER_OBJECT_PATH = '/org/chromium/Buffet/Manager'

class buffet_BasicDBusAPI(test.test):
    """Check that basic buffet daemon DBus APIs are functional."""
    version = 1

    def run_once(self):
        """Test entry point."""
        bus = dbus.SystemBus()
        buffet_proxy = bus.get_object(
                BUFFET_SERVICE_NAME, BUFFET_ROOT_OBJECT_PATH)
        # The test method has no response.
        buffet_proxy.TestMethod(dbus_interface=BUFFET_ROOT_INTERFACE)
        manager_proxy = bus.get_object(
                BUFFET_SERVICE_NAME, BUFFET_MANAGER_OBJECT_PATH)
        ticket_id = manager_proxy.RegisterDevice(
                'client_id', 'client_secret', 'api_key',
                dbus_interface=BUFFET_MANAGER_INTERFACE)
        if not ticket_id:
            raise error.TestFail('Manager.RegisterDevice should '
                                 'return a ticket id.')

        logging.info('Returned ticket id is %s.', ticket_id)
        # Updating state has no response, and we can't read the state yet,
        # because we want to expose that as a property.
        manager_proxy.UpdateState('this should be a json blob',
                                  dbus_interface=BUFFET_MANAGER_INTERFACE)
