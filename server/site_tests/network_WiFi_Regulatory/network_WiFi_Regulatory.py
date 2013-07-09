# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server import site_linux_system
from autotest_lib.server.cros import wifi_test_utils
from autotest_lib.server.cros.network import wifi_cell_test_base


class network_WiFi_Regulatory(wifi_cell_test_base.WiFiCellTestBase):
    """Test that the client vacates the channel and can no longer ping after
    notification from the AP that it should switch channels."""
    version = 1


    def parse_additional_arguments(self, commandline_args, additional_params):
        """Hook into super class to take control files parameters.

        @param commandline_args dict of parsed parameters from the autotest.
        @param additional_params list of dicts describing router configs.

        """
        self._configurations = additional_params


    def run_once(self):
        """Sets up a router, connects to it, then tests a channel switch."""
        for router_conf, alternate_channel in self._configurations:
            self.context.router.require_capabilities(
                  [site_linux_system.LinuxSystem.
                          CAPABILITY_SEND_MANAGEMENT_FRAME])
            self.context.configure(router_conf)
            assoc_params = xmlrpc_datatypes.AssociationParameters()
            assoc_params.ssid = self.context.router.get_ssid()
            self.context.assert_connect_wifi(assoc_params)
            ping_ip = self.context.get_wifi_addr(ap_num=0)
            result = self.context.client.ping(ping_ip, {}, ignore_status=True)
            for attempt in range(10):
                self.context.router.send_management_frame(
                        'channel_switch:%d' % alternate_channel)
                # This should fail at some point.  Since the client
                # might be in power-save, we are not guaranteed it will hear
                # this message the first time around.
                result = self.context.client.ping(ping_ip, {'count':3})
                stats = wifi_test_utils.parse_ping_output(result)
                if float(stats['loss']) > 60:
                    break
            else:
                raise error.TestFail('Client never lost connectivity')
            self.context.client.shill.disconnect(assoc_params.ssid)
            self.context.router.deconfig()
