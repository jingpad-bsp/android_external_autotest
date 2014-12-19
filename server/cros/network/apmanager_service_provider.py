# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.cros import constants
from autotest_lib.server.cros.network import hostap_config


class ApmanagerServiceProvider(object):
    """Provide AP service using apmanager."""

    XMLRPC_BRINGUP_TIMEOUT_SECONDS = 60

    def __init__(self, linux_system, ssid, channel=6):
        """
        @param linux_system SiteLinuxSystem machine to setup AP on.
        @param ssid string SSID of the AP.
        @param channel int Operating channel of the AP.
        """
        self._linux_system = linux_system
        self._ssid = ssid
        self._channel = channel
        self._xmlrpc_server = None
        self._service = None


    def __enter__(self):
        # Create a managed mode interface to start the AP on. Autotest removes
        # all wifi interfaces before and after each test in SiteLinuxSystem.
        self._linux_system.get_wlanif(
                hostap_config.HostapConfig.get_frequency_for_channel(
                        self._channel),
                'managed')
        self._xmlrpc_server = self._linux_system.host.xmlrpc_connect(
                constants.APMANAGER_XMLRPC_SERVER_COMMAND,
                constants.APMANAGER_XMLRPC_SERVER_PORT,
                command_name=constants.APMANAGER_XMLRPC_SERVER_CLEANUP_PATTERN,
                ready_test_name=constants.APMANAGER_XMLRPC_SERVER_READY_METHOD,
                timeout_seconds=self.XMLRPC_BRINGUP_TIMEOUT_SECONDS)
        self._service = self._xmlrpc_server.start_service(self._ssid,
                                                          self._channel)


    def __exit__(self, exception, value, traceback):
        if self._service is not None:
            self._xmlrpc_server.terminate_service(self._service)
