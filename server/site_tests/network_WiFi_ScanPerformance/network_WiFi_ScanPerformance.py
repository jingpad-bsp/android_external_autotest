# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros.network import hostap_config
from autotest_lib.server.cros.network import wifi_cell_test_base


class network_WiFi_ScanPerformance(wifi_cell_test_base.WiFiCellTestBase):
    """Performance test for scanning operation in various setup"""
    version = 1

    def run_once(self):
        """Sets up a router, scan for APs """

        # Default router configuration
        router_conf = hostap_config.HostapConfig(channel=6);

        # Scan with no AP
        ssids=[]
        self.context.client.timed_scan(frequencies=[], ssids=ssids,
                                       scan_timeout_seconds=10)

        # Scan with 1 AP
        self.context.configure(router_conf)
        ssids.append(self.context.router.get_ssid())
        self.context.client.timed_scan(frequencies=[], ssids=ssids,
                                       scan_timeout_seconds=10)

        # Scan with 2 APs on same channel
        self.context.configure(router_conf, multi_interface=True)
        ssids.append(self.context.router.get_ssid(instance=1))
        self.context.client.timed_scan(frequencies=[], ssids=ssids,
                                       scan_timeout_seconds=10)

        # Deconfigure router
        self.context.router.deconfig()

        # Scan with 2 APs on different channel
        self.context.configure(router_conf)
        router_conf.channel = 1
        self.context.configure(router_conf, multi_interface=True)
        ssids = [self.context.router.get_ssid(instance=n) for n in range(2)]
        self.context.client.timed_scan(frequencies=[], ssids=ssids,
                                       scan_timeout_seconds=10)

        # Deconfigure router
        self.context.router.deconfig()
