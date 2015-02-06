# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import json
import logging

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.tendo import buffet_config


BUFFET_SERVICE_NAME = 'org.chromium.Buffet'

BUFFET_MANAGER_INTERFACE = 'org.chromium.Buffet.Manager'
BUFFET_MANAGER_OBJECT_PATH = '/org/chromium/Buffet/Manager'

class buffet_BasicDBusAPI(test.test):
    """Check that basic buffet daemon DBus APIs are functional."""
    version = 1

    def run_once(self):
        """Test entry point."""
        buffet_config.BuffetConfig().restart_with_config()
        bus = dbus.SystemBus()
        manager_proxy = dbus.Interface(
                bus.get_object(BUFFET_SERVICE_NAME, BUFFET_MANAGER_OBJECT_PATH),
                dbus_interface=BUFFET_MANAGER_INTERFACE)

        # The test method better work.
        test_message = 'Hello world!'
        echoed_message = manager_proxy.TestMethod(test_message)
        if test_message != echoed_message:
            raise error.TestFail('Expected Manager.TestMethod to return %s '
                                 'but got %s instead.' % (test_message,
                                                          echoed_message))

        # We should get the firmware version right.
        expected_version = None
        with open('/etc/lsb-release') as f:
            for line in f.readlines():
                pieces = line.split('=', 1)
                if len(pieces) != 2:
                    continue
                key = pieces[0].strip()
                if key == 'CHROMEOS_RELEASE_VERSION':
                    expected_version = pieces[1].strip()

        if expected_version is None:
            raise error.TestError('Failed to read version from lsb-release')
        raw_state = manager_proxy.GetState()
        parsed_state = json.loads(raw_state)
        logging.debug('%r', parsed_state)
        actual_version = parsed_state['base']['firmwareVersion']
        if actual_version != expected_version:
            raise error.TestFail('Expected firmwareVersion "%s", but got "%s"' %
                                 (expected_version, actual_version))
