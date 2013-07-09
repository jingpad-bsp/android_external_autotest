# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server.cros.wlan import hostap_config
from autotest_lib.server.cros.network import wifi_cell_test_base


class network_WiFi_WMM(wifi_cell_test_base.WiFiCellTestBase):
    """Test that we can handle different QoS levels."""
    version = 1


    def run_once(self):
        """Body of the test."""
        configuration = hostap_config.HostapConfig(
                frequency=2437,
                mode=hostap_config.HostapConfig.MODE_11G,
                force_wmm=True)
        self.context.configure(configuration)
        assoc_params = xmlrpc_datatypes.AssociationParameters()
        assoc_params.ssid = self.context.router.get_ssid()
        self.context.assert_connect_wifi(assoc_params)
        for qos in ('BE', 'BK', 'VI', 'VO'):
            ping_params = {'qos': qos}
            self.context.assert_ping_from_dut(
                    additional_ping_params=ping_params)
            self.context.assert_ping_from_server(
                    additional_ping_params=ping_params)
        self.context.client.shill.disconnect(assoc_params.ssid)
        self.context.router.deconfig()
