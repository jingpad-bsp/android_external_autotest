# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server import site_linux_system
from autotest_lib.server.cros.network import wifi_cell_test_base


class network_WiFi_CSADisconnect(wifi_cell_test_base.WiFiCellTestBase):
    """Test that verifies the client's MAC 80211 queues are not stuck when
    disconnecting immediately after receiving a CSA (Channel Switch
    Announcement) message. Refer to "crbug.com/408370" for more information."""
    version = 1


    def _csa_test(self, router_initiated_disconnect):
        """Perform channel switch, and initiate disconnect immediately, then
        verify wifi connection still works, hence the 80211 queues are not
        stuck.

        @param router_initiated_disconnected bool indicating the initiator of
            the disconnect.

        """
        # Run it multiple times since the client might be in power-save,
        # we are not guaranteed it will hear this message the first time
        # around.
        for attempt in range(5):
            self.context.router.send_management_frame_on_ap(
                'channel_switch', self._alternate_channel)
            if router_initiated_disconnect:
                self.context.router.deauth_client(self._client_mac)
            else:
                self.context.client.shill.disconnect(self._assoc_params.ssid)

            # Wait for client to be disconnected.
            success, state, elapsed_seconds = \
                    self.context.client.wait_for_service_states(
                            self._assoc_params.ssid, ('idle'), 30)

            # Attempt to connect back to the AP, to make sure the MAC 80211
            # queues are not stuck.
            self.context.assert_connect_wifi(self._assoc_params)


    def parse_additional_arguments(self, commandline_args, additional_params):
        """Hook into super class to take control files parameters.

        @param commandline_args dict of parsed parameters from the autotest.
        @param additional_params list of dicts describing router configs.

        """
        self._configurations = additional_params


    def run_once(self):
        """Verify that wifi connectivity still works when disconnecting
        right after channel switch."""

        for router_conf, self._alternate_channel in self._configurations:
            self.context.router.require_capabilities(
                  [site_linux_system.LinuxSystem.
                          CAPABILITY_SEND_MANAGEMENT_FRAME])
            self.context.configure(router_conf)
            self._assoc_params = xmlrpc_datatypes.AssociationParameters()
            self._assoc_params.ssid = self.context.router.get_ssid()
            self._assoc_params.autoconnect = False
            self.context.client.shill.configure_wifi_service(self._assoc_params)
            self.context.assert_connect_wifi(self._assoc_params)
            self._client_mac = self.context.client.wifi_mac

            # Test both router initiated and client initiated disconnect after
            # channel switch announcement.
            self._csa_test(True)
            self._csa_test(False)

            self.context.client.shill.disconnect(self._assoc_params.ssid)
            self.context.router.deconfig()