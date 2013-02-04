# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib.cros.wlan import xmlrpc_datatypes
from autotest_lib.server.cros.wlan import wifi_test_base


class network_WiFi_SimpleConnect(wifi_test_base.WiFiTestBase):
    """Test that we can connect to router configured in various ways."""
    version = 1

    def parse_additional_arguments(self, commandline_args, additional_params):
        """Hook into super class to take control files parameters.

        @param commandline_args dict of parsed parameters from the autotest.
        @param additional_params list of dicts describing router configs.

        """
        self._channels = additional_params


    def run_once_impl(self):
        """Sets up a router, connects to it, pings it, and repeats."""
        for channel in self._channels:
            self.context.router.config(channel)
            assoc_params = xmlrpc_datatypes.AssociationParameters()
            assoc_params.ssid = self.context.router.get_ssid()
            self.assert_connect_wifi(assoc_params)
            self.assert_ping_from_dut()
            self.context.client.shill.disconnect(assoc_params.ssid)
            self.context.router.deconfig()
