# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import ping_runner
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server.cros.network import hostap_config
from autotest_lib.server.cros.network import wifi_cell_test_base


class network_WiFi_BgscanBackoff(wifi_cell_test_base.WiFiCellTestBase):
    """Test that background scan backs off when there is foreground traffic."""
    version = 1


    def run_once(self):
        """Body of the test."""
        ap_config = hostap_config.HostapConfig(
                frequency=2412,
                mode=hostap_config.HostapConfig.MODE_11G)
        self.context.configure(ap_config)
        bgscan_config = xmlrpc_datatypes.BgscanConfiguration()
        bgscan_config.short_interval = 7
        bgscan_config.long_interval = 7
        bgscan_config.method = 'simple'
        self.context.client.configure_bgscan(bgscan_config)
        assoc_params = xmlrpc_datatypes.AssociationParameters()
        assoc_params.ssid = self.context.router.get_ssid()
        self.context.assert_connect_wifi(assoc_params)
        period_seconds = 0.1 # Ping every 100 ms.
        duration_seconds = 10 # Ping for 10 seconds.
        count = int(duration_seconds * 1.0 / period_seconds)
        # Spend 10 seconds pinging, bgscan will hit somewhere in there.
        ping_config = ping_runner.PingConfig(self.context.get_wifi_addr(),
                                             interval=period_seconds,
                                             count=count)
        result_bgscan = self.context.client.ping(ping_config)
        logging.info('Ping statistics with bgscan: %r', result_bgscan)
        self.context.client.shill.disconnect(assoc_params.ssid)
        # No bgscan, but take 10 seconds to get some reasonable statistics.
        self.context.client.disable_bgscan()
        self.context.assert_connect_wifi(assoc_params)
        result_no_bgscan = self.context.client.ping(ping_config)
        logging.info('Ping statistics without bgscan: %r', result_no_bgscan)
        self.context.client.enable_bgscan()
        self.context.client.shill.disconnect(assoc_params.ssid)
        self.context.router.deconfig()
        # Dwell time for scanning is usually configured to be around 100 ms,
        # since this is also the standard beacon interval.  Tolerate spikes in
        # latency up to 200 ms as a way of asking that our PHY be servicing
        # foreground traffic regularly during background scans.
        if result_bgscan.max_latency > 200 + result_no_bgscan.avg_latency:
            raise error.TestFail('Significant difference in rtt due to bgscan')
