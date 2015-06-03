# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import json
import logging
import sets

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.tendo import buffet_config
from autotest_lib.client.cros import dbus_util

BUFFET_SERVICE_NAME = 'org.chromium.Buffet'

BUFFET_MANAGER_INTERFACE = 'org.chromium.Buffet.Manager'
BUFFET_MANAGER_OBJECT_PATH = '/org/chromium/Buffet/Manager'
DBUS_PROPERTY_INTERFACE = 'org.freedesktop.DBus.Properties'

class buffet_BasicDBusAPI(test.test):
    """Check that basic buffet daemon DBus APIs are functional."""
    version = 1

    def run_once(self):
        """Test entry point."""
        buffet_config.BuffetConfig().restart_with_config()
        bus = dbus.SystemBus()
        buffet_object = bus.get_object(BUFFET_SERVICE_NAME,
                                       BUFFET_MANAGER_OBJECT_PATH)
        manager_proxy = dbus.Interface(
                buffet_object,
                dbus_interface=BUFFET_MANAGER_INTERFACE)
        properties = dbus.Interface(buffet_object,
                                    DBUS_PROPERTY_INTERFACE)


        #pylint: disable=C0111
        def assert_property_equal(expected, name):
            value = dbus_util.dbus2primitive(
                    properties.Get(dbus.String(BUFFET_MANAGER_INTERFACE),
                                   dbus.String(name)))
            if expected != value:
                raise error.TestFail('Expected=%s, actual=%s' % (expected,
                                                                 value))


        assert_property_equal('', 'DeviceId')
        assert_property_equal('Chromium', 'OemName')
        assert_property_equal('Brillo', 'ModelName')
        assert_property_equal('AATST', 'ModelId')
        assert_property_equal('Developer device', 'Name')
        assert_property_equal('', 'Description')
        assert_property_equal('', 'Location')

        dbus_util.dbus2primitive(
                manager_proxy.UpdateDeviceInfo(dbus.String('A'),
                                               dbus.String('B'),
                                               dbus.String('C')))

        assert_property_equal('A', 'Name')
        assert_property_equal('B', 'Description')
        assert_property_equal('C', 'Location')

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

        state_property = dbus_util.dbus2primitive(
                properties.Get(dbus.String(BUFFET_MANAGER_INTERFACE),
                               dbus.String('State')))
        if state_property != raw_state:
            raise error.TestFail('Expected state property "%s", but got "%s"' %
                                 (raw_state, state_property))
        expected_base_keys = sets.Set(
              ['firmwareVersion', 'localDiscoveryEnabled',
               'localAnonymousAccessMaxRole', 'localPairingEnabled'])
        missing_base_keys = sets.Set(expected_base_keys).difference(
              parsed_state['base'].keys())
        if missing_base_keys:
            raise error.TestFail('Missing base keys "%s"' %  missing_base_keys)
