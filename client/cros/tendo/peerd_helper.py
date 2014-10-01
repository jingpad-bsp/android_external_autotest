# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import dbus.mainloop.glib
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils


# DBus constants for use with peerd.
SERVICE_NAME = 'org.chromium.peerd'
DBUS_PATH_MANAGER = '/org/chromium/peerd/Manager'
DBUS_INTERFACE_MANAGER = 'org.chromium.peerd.Manager'

# Possible technologies for use with PeerdHelper.start_monitoring().
TECHNOLOGY_MDNS = 'm_dns'
TECHNOLOGY_WIFI_SSID = 'wifi_ssid'
TECHNOLOGY_BT_LE = 'bt_le'
TECHNOLOGY_BT = 'bt_classic'
TECHNOLOGY_ALL = 'all'


def make_helper(bus=None, start_instance=False, timeout_seconds=10,
                verbosity_level=0):
    """Wait for peerd to come up, then return a PeerdHelper for it.

    @param bus: DBus bus to use, or specify None to create one internally.
    @param start_instance: bool True if we should start a peerd instance.
    @param timeout_seconds: number of seconds to wait for peerd to come up.
    @param verbosity_level: int level of log verbosity from peerd (e.g. 0
                            will log INFO level, 3 is verbosity level 3).
    @return PeerdHelper instance if peerd comes up, None otherwise.

    """
    pid_to_kill = None
    if start_instance:
        result = utils.run('peerd --v=%d & echo $!' % verbosity_level)
        pid_to_kill = int(result.stdout)
    else:
        # TODO(wiley) Add a verbosity switch to peerd, call it here.
        pass
    if bus is None:
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SystemBus()
    end_time = time.time() + timeout_seconds
    connection = None
    while time.time() < end_time:
        if not bus.name_has_owner(SERVICE_NAME):
            time.sleep(0.2)
        return PeerdHelper(bus, pid_to_kill)
    raise error.TestFail('peerd did not start in a timely manner.')


class PeerdHelper(object):
    """Container for convenience methods related to peerd."""

    def __init__(self, bus, peerd_pid_to_kill):
        """Construct a PeerdHelper.

        @param bus: DBus bus to use, or specify None and this object will
                    create a mainloop and bus.
        @param peerd_pid_to_kill: pid to kill on close() or None.

        """
        self._bus = bus
        self._pid = peerd_pid_to_kill
        self._manager = dbus.Interface(
                self._bus.get_object(SERVICE_NAME, DBUS_PATH_MANAGER),
                DBUS_INTERFACE_MANAGER)


    def close(self):
        """Clean up peerd state related to this helper.

        Removes related services and monitoring requests.
        Optionally kills the peerd instance if we created this instance.

        """
        if self._pid is not None:
            utils.run('kill %d' % self._pid, ignore_status=True)
            self._pid = None


    def start_monitoring(self, technologies):
        """Monitor the specified technologies.

        Note that peerd will watch bus connections and stop monitoring a
        technology if this bus connection goes away.A

        @param technologies: iterable container of TECHNOLOGY_* defined above.
        @return string monitoring_token for use with stop_monitoring().

        """
        return self._manager.StartMonitoring(technologies)


    def expose_service(self, service_id, service_info):
        """Expose a service via peerd.

        Note that peerd should watch DBus connections and remove this service
        if our bus connection ever goes down.

        @param service_id: string id of service.  See peerd documentation
                           for limitations on this string.
        @param service_info: dict of string, string entries.  See peerd
                             documentation for relevant restrictions.
        @return string service token for use with remove_service().

        """
        return self._manager.ExposeService(service_id, service_info)


    def remove_service(self, service_token):
        """Remove a service previously added via expose_service().

        @param service_token: string token returned by expose_service().

        """
        self._manager.RemoveExposedService(service_token)
