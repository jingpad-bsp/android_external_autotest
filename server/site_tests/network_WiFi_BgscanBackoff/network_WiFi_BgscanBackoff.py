# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server.cros.wlan import hostap_config
from autotest_lib.server.cros.network import wifi_cell_test_base
from autotest_lib.server.cros import wifi_test_utils


class network_WiFi_BgscanBackoff(wifi_cell_test_base.WiFiCellTestBase):
    """Test that background scan backs off when there is foreground traffic."""
    version = 1


    @staticmethod
    def _compare_stats(stats0, stats1):
        """Compare two sets of ping statistics to ensure they are 'similar.'

        Comments inline.

        @param stats0 dict of stats returned by parse_ping_output().
        @param stats1 dict of stats returned by parse_ping_output().

        """
        if 'dev' not in stats0 or 'dev' not in stats1:
            raise error.TestFail('Missing standard dev from ping stats')
        if 'min' not in stats0 or 'min' not in stats1:
            raise error.TestFail('Missing max rtt from ping stats')
        if 'avg' not in stats0 or 'avg' not in stats1:
            raise error.TestFail('Missing avg rtt from ping stats')
        if 'max' not in stats0 or 'max' not in stats1:
            raise error.TestFail('Missing max rtt from ping stats')
        try:
            avg0 = float(stats0['avg'])
            max0 = float(stats0['max'])
            avg1 = float(stats1['avg'])
            max1 = float(stats1['max'])
        except ValueError:
            raise error.TestFail('Failed to parse ping statistics from avg/max '
                                 'pairs: %s/%s %s/%s',
                                 stats0['avg'], stats0['max'],
                                 stats1['avg'], stats1['max'])
        # This check is meant to assert that ping latency remains 'similar'
        # during WiFi background scans.  APs typically send beacons every 100ms,
        # (the period is configurable) so bgscan algorithms like to sit in a
        # channel for 100ms to see if they can catch a beacon.
        #
        # Assert that the maximum latency is under 200 ms + whatever the
        # average was for the other sample.  This allows us to go off chanel,
        # but forces us to serve some real traffic when we go back on.
        # We'll do this check symmetrically because we don't actually know
        # which is the control distribution and which is the potentially dirty
        # distribution.
        if max0 > 200 + avg1 or max1 > 200 + avg0:
            raise error.TestFail('Significant difference in rtt due to bgscan')


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
        ping_output = self.context.client.ping(self.context.get_wifi_addr(),
                                               {'interval': period_seconds},
                                               count=count)
        stats_with_bgscan = wifi_test_utils.parse_ping_output(ping_output)
        logging.info('Ping statistics with bgscan: %r', stats_with_bgscan)
        self.context.client.shill.disconnect(assoc_params.ssid)
        # No bgscan, but take 10 seconds to get some reasonable statistics.
        self.context.client.disable_bgscan()
        self.context.assert_connect_wifi(assoc_params)
        ping_output = self.context.client.ping(self.context.get_wifi_addr(),
                                               {'interval': period_seconds},
                                               count=count)
        self.context.client.enable_bgscan()
        stats_without_bgscan = wifi_test_utils.parse_ping_output(ping_output)
        logging.info('Ping statistics without bgscan: %r', stats_without_bgscan)
        self._compare_stats(stats_with_bgscan, stats_without_bgscan)
        self.context.client.shill.disconnect(assoc_params.ssid)
        self.context.router.deconfig()
