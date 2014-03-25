# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import json
import logging

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


BUFFET_SERVICE_NAME = 'org.chromium.Buffet'

BUFFET_ROOT_INTERFACE = 'org.chromium.Buffet'
BUFFET_ROOT_OBJECT_PATH = '/org/chromium/Buffet'

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

        logging.info('Getting state via GetAll()')
        properties = manager_proxy.GetAll(BUFFET_MANAGER_INTERFACE,
                                          dbus_interface=dbus.PROPERTIES_IFACE)
        if 'State' not in properties:
            raise error.TestFail('Manager should have a State property.')

        logging.info('Getting state via Get()')
        state_property = manager_proxy.Get(BUFFET_MANAGER_INTERFACE, 'State',
                                           dbus_interface=dbus.PROPERTIES_IFACE)
        if state_property != properties['State']:
            raise error.TestFail('State property from GetAll does not match '
                                 'Get: (%s vs %s).' % (properties['State'],
                                                       state_property))

        logging.info('Updating state.')
        manager_proxy.UpdateState(
                json.dumps({TEST_STATE_KEY: TEST_STATE_VALUE}),
                dbus_interface=BUFFET_MANAGER_INTERFACE)
