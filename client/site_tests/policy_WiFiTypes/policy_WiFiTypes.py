# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.enterprise import enterprise_policy_base
from autotest_lib.client.cros.enterprise import enterprise_network_api


class policy_WiFiTypes(enterprise_policy_base.EnterprisePolicyTest):
    version = 1


    def cleanup(self):
        """Re-enable ethernet after the test is completed."""
        if hasattr(self, 'net_api'):
            self.net_api.chrome_net_context.enable_network_device('Ethernet')
        super(policy_WiFiTypes, self).cleanup()


    def run_once(self, ssid='', security=None, eap=None, password=None,
                 identity=None, ca_cert=None, client_cert=None):
        """
        Setup and run the test configured for the specified test case.

        @param ssid: Service set identifier for wireless local area network.
        @param security: Security of network. Options are:
            'None', 'WEP-PSK', 'WEP-8021X', 'WPA-PSK', and 'WPA-EAP'.
        @param eap: EAP type, required if security is 'WEP-8021X' or 'WPA-EAP'.
        @param identity: Username, if the network type requires it.
        @param password: Password, if the network type requires it.
        @param ca_cert: CA certificate in PEM format. Required
            for EAP networks.
        @param client_cert: Client certificate in base64 encoded PKCS#12
            format.

        """
        # Test with both autoconnect on and off.
        for autoconnect in [False, True]:
            network_policy = enterprise_network_api.create_network_policy(
                ssid,
                security=security,
                eap=eap,
                password=password,
                identity=identity,
                autoconnect=autoconnect,
                ca_cert=ca_cert,
                client_cert=client_cert
            )

            self.setup_case(
                user_policies={'OpenNetworkConfiguration': network_policy},
                extension_paths=[
                        enterprise_network_api.NETWORK_TEST_EXTENSION_PATH
                ],
            )

            self.net_api = enterprise_network_api.\
                ChromeEnterpriseNetworkContext(self.cr)
            # Disable ethernet so device will default to WiFi
            self.net_api.disable_network_device('Ethernet')

            if not autoconnect:
                self.net_api.connect_to_network(ssid)

            if not self.net_api.is_network_connected(ssid):
                raise error.TestFail(
                        'No connection to network (%s) when autoconnect is %s.'
                        % (ssid, autoconnect))
