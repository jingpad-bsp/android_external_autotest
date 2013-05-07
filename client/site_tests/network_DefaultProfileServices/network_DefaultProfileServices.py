# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from dbus import DBusException

# This hacks the path so that we can import shill_proxy.
# pylint: disable=W0611
from autotest_lib.client.cros import flimflam_test_path
# pylint: enable=W0611
import shill_proxy

class network_DefaultProfileServices(test.test):
    """The Default Profile Services class.

    Wipe the default profile, start shill, configure a service, restart
    shill, and check that the service exists.

    The service name is chosen such that it is unlikely match any SSID
    that is present over-the-air.

    """
    DEFAULT_PROFILE_PATH="/var/cache/shill/default.profile"
    OUR_SSID="org.chromium.DfltPrflSrvcsTest"
    DBUS_SERVICE_UNKNOWN="org.freedesktop.DBus.Error.ServiceUnknown"
    version = 1

    def stop_shill(self):
        """Stop the running shill process"""
        os.system("stop shill")

    def start_shill(self):
        """Start a shill process. Assumes it is not already running"""
        os.system("start shill")

    def delete_default_profile(self):
        """Remove shill's default profile."""
        os.remove(self.DEFAULT_PROFILE_PATH)

    def connect_proxy(self):
        """Connect to shill over D-Bus. If shill is not yet running,
           retry until it is."""
        self._shill = None
        while self._shill is None:
            try:
                self._shill = shill_proxy.ShillProxy()
            except DBusException as e:
                if e.get_dbus_name() != self.DBUS_SERVICE_UNKNOWN:
                    raise error.TestFail("Error connecting to shill")

    def run_once(self):
        """Test main loop."""
        self.stop_shill()
        self.delete_default_profile()
        self.start_shill()
        self.connect_proxy()

        manager = self._shill.manager
        manager.PopAllUserProfiles()
        path = manager.ConfigureService({
                self._shill.SERVICE_PROPERTY_TYPE: "wifi",
                self._shill.SERVICE_PROPERTY_MODE: "managed",
                self._shill.SERVICE_PROPERTY_SSID: self.OUR_SSID,
                self._shill.SERVICE_PROPERTY_HIDDEN: True,
                self._shill.SERVICE_PROPERTY_SECURITY: "none",
                })

        self.stop_shill()
        self.start_shill()
        self.connect_proxy()
        manager = self._shill.manager
        manager.PopAllUserProfiles()
        service = self._shill.find_object('AnyService',
                                          {'Name': self.OUR_SSID})
        if not service:
            raise error.TestFail("Network not found after restart.")
