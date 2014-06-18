# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server.cros.network import wifi_cell_test_base


class network_WiFi_SimpleConnect(wifi_cell_test_base.WiFiCellTestBase):
    """Test that we can connect to router configured in various ways."""
    version = 1

    def parse_additional_arguments(self, commandline_args, additional_params):
        """Hook into super class to take control files parameters.

        @param commandline_args dict of parsed parameters from the autotest.
        @param additional_params list of tuple(HostapConfig,
                                               AssociationParameters).

        """
        self._configurations = additional_params


    def run_once(self):
        """Sets up a router, connects to it, pings it, and repeats."""
        for router_conf, client_conf in self._configurations:
            self.context.configure(router_conf)
            client_conf.ssid = self.context.router.get_ssid()
            self.context.assert_connect_wifi(client_conf)
            if client_conf.expect_failure:
                logging.info('Skipping ping because we expected this '
                             'attempt to fail.')
            else:
                self.context.assert_ping_from_dut()
                self.context.client.shill.disconnect(client_conf.ssid)
            self.context.client.shill.delete_entries_for_ssid(client_conf.ssid)
            self.context.router.deconfig()
