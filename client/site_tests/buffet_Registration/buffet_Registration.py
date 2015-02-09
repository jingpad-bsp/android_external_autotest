# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import logging

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib.cros import process_watcher
from autotest_lib.client.common_lib.cros.fake_device_server.client_lib import \
        registration
from autotest_lib.client.common_lib.cros.tendo import buffet_config


TEST_DEVICE_KIND = 'test_device_kind'
TEST_DEVICE_NAME = 'test_device_name'
TEST_DISPLAY_NAME = 'test_display_name '
TEST_DESCRIPTION = 'test_description '
TEST_LOCATION = 'test_location '

class buffet_Registration(test.test):
    """Test that buffet can go through registration against a fake server."""

    version = 1

    def run_once(self, use_prod=False):
        """Test entry point."""
        self._gcd = process_watcher.ProcessWatcher(
                '/usr/local/autotest/common_lib/cros/'
                        'fake_device_server/server.py')
        self._gcd.start()
        buffet_config.BuffetConfig(log_verbosity=3).restart_with_config()
        registration_client = registration.RegistrationClient(
                server_url=buffet_config.LOCAL_SERVICE_URL,
                api_key=buffet_config.TEST_API_KEY)
        ticket = registration_client.create_registration_ticket()
        logging.info('Created ticket: %r', ticket)
        bus = dbus.SystemBus()
        manager_proxy = dbus.Interface(
                bus.get_object(buffet_config.SERVICE_NAME,
                               buffet_config.MANAGER_OBJECT_PATH),
                dbus_interface=buffet_config.MANAGER_INTERFACE)
        registration_params = dbus.Dictionary(signature='sv')
        registration_params.update({
                'ticket_id': ticket['id'],
                'device_kind': TEST_DEVICE_KIND,
                'name': TEST_DEVICE_NAME,
                'display_name': TEST_DISPLAY_NAME,
                'description': TEST_DESCRIPTION,
                'location': TEST_LOCATION,
        })
        manager_proxy.RegisterDevice(registration_params)

    def cleanup(self):
        buffet_config.BuffetConfig.naive_restart()
        self._gcd.close()
