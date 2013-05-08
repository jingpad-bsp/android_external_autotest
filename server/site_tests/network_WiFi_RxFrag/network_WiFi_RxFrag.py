# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server.cros.wlan import hostap_config
from autotest_lib.server.cros.wlan import wifi_cell_test_base


class network_WiFi_RxFrag(wifi_cell_test_base.WiFiCellTestBase):
    """Test that the DUT can reassemble packet fragments."""
    version = 1


    def run_once_impl(self):
        """Test body.

        When fragthreshold is set, packets larger than the threshold are
        broken up by the AP and sent in fragments. The DUT needs to reassemble
        these fragments to reconstruct the original packets before processing
        them.

        """
        configuration = hostap_config.HostapConfig(
                frequency=2437,
                mode=hostap_config.HostapConfig.MODE_11G,
                frag_threshold=256)
        self.context.configure(configuration)
        assoc_params = xmlrpc_datatypes.AssociationParameters()
        assoc_params.ssid = self.context.router.get_ssid()
        self.assert_connect_wifi(assoc_params)
        self.assert_ping_from_server(additional_ping_params={'size': 256})
        self.assert_ping_from_server(additional_ping_params={'size': 512})
        self.assert_ping_from_server(additional_ping_params={'size': 1024})
        self.assert_ping_from_server(additional_ping_params={'size': 1500})
        self.context.client.shill.disconnect(assoc_params.ssid)
        self.context.router.deconfig()
