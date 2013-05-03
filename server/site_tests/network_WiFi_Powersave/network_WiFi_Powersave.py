# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server.cros.wlan import hostap_config
from autotest_lib.server.cros.wlan import wifi_test_base


class network_WiFi_Powersave(wifi_test_base.WiFiTestBase):
    """Test that we can enter and exit powersave mode without issue."""
    version = 1


    def run_once_impl(self):
        """Test body.

        Powersave mode takes advantage of DTIM intervals, and so the two
        are intimately tied.  See network_WiFi_DTIMPeriod for a discussion
        of their interaction.

        """
        dtim_val = 5
        configuration = hostap_config.HostapConfig(
                frequency=2437,
                mode=hostap_config.HostapConfig.MODE_11G,
                dtim_period=dtim_val)
        self.context.configure(configuration)
        self.context.client.check_powersave(False)
        assoc_params = xmlrpc_datatypes.AssociationParameters()
        assoc_params.ssid = self.context.router.get_ssid()
        self.context.client.powersave_switch(True)
        self.context.client.check_powersave(True)
        self.assert_connect_wifi(assoc_params)
        self.assert_ping_from_dut()
        self.assert_ping_from_server()
        self.context.client.shill.disconnect(assoc_params.ssid)
        self.context.client.powersave_switch(False)
        self.context.client.check_powersave(False)
        self.context.router.deconfig()
