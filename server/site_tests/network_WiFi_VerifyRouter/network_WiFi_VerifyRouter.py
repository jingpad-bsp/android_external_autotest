# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server import site_linux_system
from autotest_lib.server.cros.network import hostap_config
from autotest_lib.server.cros.network import wifi_cell_test_base


class network_WiFi_VerifyRouter(wifi_cell_test_base.WiFiCellTestBase):
    """Test that a dual radio router can use both radios."""
    version = 1


    def run_once(self):
        """Set up two APs connect to both and then exit."""
        self.context.router.require_capabilities(
                [site_linux_system.LinuxSystem.CAPABILITY_MULTI_AP_SAME_BAND])
        ap_config = hostap_config.HostapConfig(channel=6)
        # Create an AP, manually specifying both the SSID and BSSID.
        self.context.configure(ap_config)
        self.context.configure(ap_config, multi_interface=True)
        for instance in range(2):
            client_conf = xmlrpc_datatypes.AssociationParameters(
                    ssid=self.context.router.get_ssid(instance=instance))
            self.context.assert_connect_wifi(client_conf)
