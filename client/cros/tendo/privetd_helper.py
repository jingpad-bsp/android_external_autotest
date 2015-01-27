# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import os.path
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.cros import dbus_util

DBUS_PROPERTY_INTERFACE = 'org.freedesktop.DBus.Properties'

SERVICE_NAME = 'org.chromium.privetd'
MANAGER_INTERFACE = 'org.chromium.privetd.Manager'
MANAGER_OBJECT_PATH = '/org/chromium/privetd/Manager'

BOOTSTRAP_CONFIG_DISABLED = 'off'
BOOTSTRAP_CONFIG_AUTOMATIC = 'automatic'
BOOTSTRAP_CONFIG_MANUAL = 'manual'

WIFI_BOOTSTRAP_STATE_DISABLED = 'disabled'
WIFI_BOOTSTRAP_STATE_WAITING = 'waiting'
WIFI_BOOTSTRAP_STATE_CONNECTING = 'connecting'
WIFI_BOOTSTRAP_STATE_MONITORING = 'monitoring'

PRIVETD_CONF_FILE_PATH = '/tmp/privetd.conf'
PRIVETD_TEMP_STATE_FILE = '/tmp/privetd.state'

def privetd_is_installed():
    """@return True iff privetd is installed in this system."""
    if os.path.exists('/usr/bin/privetd'):
        return True
    return False


def make_helper(apply_settings_and_restart=True,
                wifi_bootstrap_mode=BOOTSTRAP_CONFIG_DISABLED,
                gcd_bootstrap_mode=BOOTSTRAP_CONFIG_DISABLED,
                monitor_timeout_seconds=120,
                connect_timeout_seconds=60,
                bootstrap_timeout_seconds=300,
                verbosity_level=None,
                separate_state=True,
                timeout_seconds=5):
    """Create a PrivetdHelper object.

    @param apply_settings_and_restart: bool False to ignore every other
            paramter, since we can't apply new configuration without
            restarting privetd.
    @param wifi_bootstrap_mode: one of BOOTSTRAP_CONFIG_* above.
    @param gcd_bootstrap_mode: one of BOOTSTRAP_CONFIG_* above.
    @param monitor_timeout_seconds: int timeout for the WiFi bootstrapping
            state machine.
    @param connect_timeout_seconds: int timeout for the WiFi bootstrapping
            state machine.
    @param bootstrap_timeout_seconds: int timeout for the WiFi bootstrapping
            state machine.
    @param verbosity_level: int logging verbosity for privetd.
    @param separate_state: bool True to cause privetd to use a temporary,
            fresh state file.
    @param timeout_seconds: number of seconds to wait for privetd to come
            up after restarting it with new configuration settings.

    """
    if apply_settings_and_restart:
        conf_dict = {
                'bootstrapping_mode': wifi_bootstrap_mode,
                'gcd_bootstrapping_mode': gcd_bootstrap_mode,
                'monitor_timeout_seconds': monitor_timeout_seconds,
                'connect_timeout_seconds': connect_timeout_seconds,
                'bootstrap_timeout_seconds': bootstrap_timeout_seconds,
        }
        if separate_state:
            conf_dict['state_file'] = PRIVETD_TEMP_STATE_FILE
            utils.run('echo > %s' % PRIVETD_TEMP_STATE_FILE)
            utils.run('chown privetd:privetd %s' % PRIVETD_TEMP_STATE_FILE)
        with open(PRIVETD_CONF_FILE_PATH, 'w') as f:
            f.writelines(['%s=%s\n' % item for item in conf_dict.iteritems()])
        utils.run('chown privetd:privetd %s' % PRIVETD_CONF_FILE_PATH)
        flag_dict = {}
        if verbosity_level is not None:
            flag_dict['PRIVETD_LOG_LEVEL'] = str(verbosity_level)
        flag_dict['PRIVETD_CONFIG_PATH'] = PRIVETD_CONF_FILE_PATH
        flag_str = ' '.join(['%s=%s' % item for item in flag_dict.iteritems()])
        utils.run('stop privetd', ignore_status=True)
        utils.run('start privetd %s' % flag_str)
    bus = dbus.SystemBus()
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        try:
            manager_proxy = bus.get_object(SERVICE_NAME, MANAGER_OBJECT_PATH)
            return PrivetdHelper(manager_proxy, apply_settings_and_restart)
        except dbus.exceptions.DBusException, e:
            time.sleep(0.2)
    # Failure, clean up our state before failing the test
    utils.run('stop privetd', ignore_status=True)
    utils.run('start privetd')
    raise error.TestError('Failed to construct DBus proxy to privetd.')


class PrivetdHelper(object):
    """Delegate representing an instance of privetd."""

    def __init__(self, manager_proxy, restart_on_close):
        """Construct a PrivetdHelper.

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


    def close(self):
        """Clean up state related to this instance of privetd."""
        if self._restart_on_close:
            utils.run('stop privetd')
            utils.run('start privetd')
