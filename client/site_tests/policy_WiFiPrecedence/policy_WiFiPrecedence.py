# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import pickle

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.enterprise import enterprise_policy_base
from autotest_lib.client.cros.enterprise import enterprise_network_api


class policy_WiFiPrecedence(enterprise_policy_base.EnterprisePolicyTest):
    version = 1


    def cleanup(self):
        """Re-enable ethernet after the test is completed."""
        if hasattr(self, 'net_api'):
            self.net_api.chrome_net_context.enable_network_device('Ethernet')
        super(policy_WiFiPrecedence, self).cleanup()


    def test_precedence(self, user_network, device_network, precedence, test):
        """
        Ensure DUT connects to network with higher precedence.

        DUT is given 2 network configs and must connect to the one specified
        by |precedence|.

        @param user_network: A NetworkConfig object representing the
            user network.
        @param device_network: A NetworkConfig object representing the
            device network.
        @param precedence: The string 'user' or 'device' that indicates
            which network should autoconnect.
        @param test: Name of the test being run.

        @raises error.TestFail: If DUT does not connect to the |precedence|
            network.

        """
        if test == 'managed_vs_unmanaged':
            # Connect and disconnect from the unmanaged network so the network
            # is a "remembered" network on the DUT.
            self.net_api.connect_to_network(device_network.ssid)
            self.net_api.disconnect_from_network(device_network.ssid)

        # If the user and device network are the same, ignore the
        # precedence checks.
        if user_network.ssid != device_network.ssid:
            if (self.net_api.is_network_connected(user_network.ssid) and
                    precedence == 'device'):
                raise error.TestError(
                        'DUT autoconnected to user network, but '
                        'should have preferred the device network.')
            elif (self.net_api.is_network_connected(device_network.ssid) and
                  precedence == 'user'):
                raise error.TestError(
                        'DUT autoconnected to device network, but '
                        'should have preferred the user network.')

        if (not self.net_api.is_network_connected(user_network.ssid) and
              not self.net_api.is_network_connected(device_network.ssid)):
            raise error.TestError('DUT did not connect to a network.')


    def run_once(self, user_network_pickle=None, device_network_pickle=None,
                 precedence=None, test=None):
        """
        Setup and run the test configured for the specified test case.

        @param user_network_pickle: A pickled version of a NetworkConfig
            object representing the user network.
        @param device_network_pickle: A pickled version of a NetworkConfig
            object representing the device network.
        @param precedence: The string 'user' or 'device' that indicates
            which network should autoconnect.
        @param test: Name of the test being run.

        @raises error.TestFail: If DUT does not connect to the |precedence|
            network.

        """
        user_network = pickle.loads(user_network_pickle)
        device_network = pickle.loads(device_network_pickle)

        # For the unmanaged network test, don't set a device policy for the
        # unmanaged network.
        device_policy = {}
        if test != 'managed_vs_unmanaged':
            device_policy['device_policies'] = {
                'DeviceOpenNetworkConfiguration': device_network.policy()
            }

        self.setup_case(
            user_policies={
                'OpenNetworkConfiguration': user_network.policy()
            },
            extension_paths=[
                enterprise_network_api.NETWORK_TEST_EXTENSION_PATH
            ],
            enroll=True,
            **device_policy
        )

        self.net_api = enterprise_network_api.\
            ChromeEnterpriseNetworkContext(self.cr)
        # Disable ethernet so device will default to WiFi.
        self.net_api.disable_network_device('Ethernet')

        self.test_precedence(user_network, device_network, precedence, test)
