# Copyright (c) 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server import autotest
from autotest_lib.server import site_linux_system
from autotest_lib.server.cros.network import wifi_cell_test_base


class policy_WiFiTypesServer(wifi_cell_test_base.WiFiCellTestBase):
    version = 1


    def run_once(self, host, ap_config, security=None, eap=None, password=None,
                 identity=None, autoconnect=None, ca_cert=None):
        """
        Set up an AP for a WiFi authentication type then run the client test.

        @param host: A host object representing the DUT.
        @param ap_config: HostapConfig object representing how to configure
            the router.
        @param security: Security of network. Options are:
            'None', 'WEP-PSK', 'WEP-8021X', 'WPA-PSK', and 'WPA-EAP'.
        @param eap: EAP type, required if security is 'WEP-8021X' or 'WPA-EAP'.
        @param identity: Username, if the network type requires it.
        @param password: Password, if the network type requires it.
        @param ca_cert: CA certificate in PEM format. Required
            for EAP networks.
        @param autoconnect: True iff network policy should autoconnect.

        """
        self.context.router.require_capabilities(
                [site_linux_system.LinuxSystem.CAPABILITY_MULTI_AP])
        self.context.router.deconfig()

        # Configure the AP
        self.context.configure(ap_config)

        client_at = autotest.Autotest(host)
        client_at.run_test('policy_WiFiTypes',
                           ssid=self.context.router.get_ssid(),
                           security=security,
                           eap=eap,
                           password=password,
                           identity=identity,
                           autoconnect=autoconnect,
                           ca_cert=ca_cert,
                           check_client_result=True)

        self.context.router.deconfig()
