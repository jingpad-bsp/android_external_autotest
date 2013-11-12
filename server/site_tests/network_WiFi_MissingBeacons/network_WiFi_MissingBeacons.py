# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server.cros.network import hostap_config
from autotest_lib.server.cros.network import wifi_cell_test_base


class network_WiFi_MissingBeacons(wifi_cell_test_base.WiFiCellTestBase):
    """Test how a DUT behaves when an AP disappears suddenly.

    Connects a DUT to an AP, then kills the AP in such a way that no de-auth
    message is sent.  Asserts that the DUT marks itself as disconnected from
    the AP within MAX_DISCONNECT_TIME_SECONDS.

    """

    version = 1

    MAX_DISCONNECT_TIME_SECONDS = 20


    def _assert_disconnect(self, ssid):
        """Assert that we disconnect from |ssid| MAX_DISCONNECT_TIME_SECONDS.

        @param ssid: string ssid of network we expect to be disconnected from.

        """
        # Leave some margin of seconds to check how long it actually
        # takes to disconnect should we fail to disconnect in time.
        timeout_seconds = self.MAX_DISCONNECT_TIME_SECONDS + 10
        logging.info('Waiting %.2f seconds for client to notice the missing '
                     'AP.', timeout_seconds)
        result = self.context.client.wait_for_service_states(
                ssid, ['idle'], timeout_seconds=timeout_seconds)
        success, state, duration_seconds = result
        if not success or duration_seconds > self.MAX_DISCONNECT_TIME_SECONDS:
            raise error.TestFail('Timed out waiting disconnect in %f '
                                 'seconds.  Ended in %s' %
                                 (duration_seconds, state))
        else:
            logging.info('Client detected the AP absence in %.2f seconds',
                         duration_seconds)


    def run_once(self):
        """Body of the test."""
        ap_config = hostap_config.HostapConfig(channel=1)
        self.context.configure(ap_config)
        ssid = self.context.router.get_ssid()
        client_config = xmlrpc_datatypes.AssociationParameters(ssid=ssid)
        self.context.assert_connect_wifi(client_config)
        self.context.assert_ping_from_dut()
        self.context.router.deconfig_aps(silent=True)
        self._assert_disconnect(ssid)
        logging.info('Repeating test with a client scan just before AP death.')
        self.context.configure(ap_config)
        ssid = self.context.router.get_ssid()
        client_config = xmlrpc_datatypes.AssociationParameters(ssid=ssid)
        self.context.assert_connect_wifi(client_config)
        self.context.assert_ping_from_dut()
        self.context.client.scan(frequencies=[], ssids=[])
        self.context.router.deconfig_aps(silent=True)
        self._assert_disconnect(ssid)
