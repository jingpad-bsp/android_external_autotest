# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.client.common_lib.cros.network  import xmlrpc_security_types
from autotest_lib.server.cros.wlan import hostap_config
from autotest_lib.server.cros.wlan import wifi_cell_test_base


class network_WiFi_PTK(wifi_cell_test_base.WiFiCellTestBase):
    version = 1

    # These settings combine to give us around 30 seconds of ping time,
    # which should be around 6 rekeys.
    PING_COUNT = 150
    PING_INTERVAL = 0.2
    REKEY_PERIOD = 5


    def run_once(self):
        """Test body."""
        wpa_config = xmlrpc_security_types.WPAConfig(
                psk='chromeos',
                wpa_mode=xmlrpc_security_types.WPAConfig.MODE_MIXED_WPA,
                wpa_ciphers=[xmlrpc_security_types.WPAConfig.CIPHER_TKIP,
                             xmlrpc_security_types.WPAConfig.CIPHER_CCMP],
                wpa2_ciphers=[xmlrpc_security_types.WPAConfig.CIPHER_CCMP],
                wpa_ptk_rekey_period=self.REKEY_PERIOD)
        ap_config = hostap_config.HostapConfig(
                    frequency=2412,
                    mode=hostap_config.HostapConfig.MODE_11N_PURE,
                    security_config=wpa_config)
        self.context.configure(ap_config)
        assoc_params = xmlrpc_datatypes.AssociationParameters()
        assoc_params.ssid = self.context.router.get_ssid()
        assoc_params.security_config = wpa_config
        self.context.assert_connect_wifi(assoc_params)
        ping_params = {'count': self.PING_COUNT,
                       'interval': self.PING_INTERVAL}
        logging.info('Pinging DUT for %d seconds and rekeying '
                     'every %d seconds.' %
                     (self.PING_COUNT * self.PING_INTERVAL,
                      self.REKEY_PERIOD))
        self.context.assert_ping_from_dut(additional_ping_params=ping_params)
        logging.info('Ping successful.')
        self.context.client.shill.disconnect(assoc_params.ssid)
        self.context.router.deconfig()
