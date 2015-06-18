# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.cros import dbus_util

DBUS_PROPERTY_INTERFACE = 'org.freedesktop.DBus.Properties'

SERVICE_NAME = 'org.chromium.privetd'
MANAGER_INTERFACE = 'org.chromium.privetd.Manager'
MANAGER_OBJECT_PATH = '/org/chromium/privetd/Manager'

def make_dbus_helper(privetd_config, timeout_seconds=5):
    """Create a PrivetdDBusHelper object.

    @param privetd_config: PrivetdConfig instance or None to reuse a
            running privetd instance.
    @param timeout_seconds: number of seconds to wait for privetd to come
            up after restarting it with new configuration settings.

    """
    if privetd_config is not None:
        privetd_config.restart_with_config()
    bus = dbus.SystemBus()
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        try:
            manager_proxy = bus.get_object(SERVICE_NAME, MANAGER_OBJECT_PATH)
            return PrivetdDBusHelper(manager_proxy, privetd_config is not None)
        except dbus.exceptions.DBusException, e:
            time.sleep(0.2)
    # Failure, clean up our state before failing the test
    utils.run('stop privetd', ignore_status=True)
    utils.run('start privetd')
    raise error.TestError('Failed to construct DBus proxy to privetd.')


class PrivetdDBusHelper(object):
    """Delegate representing an instance of privetd."""

    def __init__(self, manager_proxy, restart_on_close):
        """Construct a PrivetdDBusHelper.

        You should probably use get_helper() above rather than call this
        directly.

        @param manager_proxy: DBus proxy for the Manager object.

        """
        self.manager = dbus.Interface(manager_proxy, MANAGER_INTERFACE)
        self.manager_properties = dbus.Interface(
                manager_proxy, DBUS_PROPERTY_INTERFACE)
        self._restart_on_close = restart_on_close


    @property
    def wifi_bootstrap_status(self):
        """@return string DBus exposed bootstrapping state for WiFi."""
        state = self.manager_properties.Get(
                MANAGER_INTERFACE, 'WiFiBootstrapState')
        return dbus_util.dbus2primitive(state)


    @property
    def pairing_info(self):
        """@return string DBus exposed bootstrapping state for WiFi."""
        pairing_info = self.manager_properties.Get(
                MANAGER_INTERFACE, 'PairingInfo')
        return dbus_util.dbus2primitive(pairing_info)
