# Copyright (c) 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import iw_runner
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server.cros.network import wifi_cell_test_base
from autotest_lib.server.cros.network import hostap_config

class network_WiFi_RoamFT(wifi_cell_test_base.WiFiCellTestBase):
    """Tests roam on low signal using FT-PSK between APs

    This test seeks to associate the DUT with an AP with a set of
    association parameters, create a second AP with a second set of
    parameters but the same SSID, and lower the transmission power of
    the first AP. We seek to observe that the DUT successfully
    connects to the second AP in a reasonable amount of time.

    Roaming using FT-PSK is different from standard roaming in that
    there is a special key exchange protocol that needs to occur
    between the APs prior to a successful roam. In order for this
    communication to work, we need to construct a specific interface
    architecture as shown below:
                 _________                       _________
                |         |                     |         |
                |   br0   |                     |   br1   |
                |_________|                     |_________|
                   |   |                           |   |
               ____|   |____                   ____|   |____
         _____|____     ____|____         ____|____     ____|_____
        |          |   |         |       |         |   |          |
        | managed0 |   |  veth0  | <---> |  veth1  |   | managed1 |
        |__________|   |_________|       |_________|   |__________|

    The managed0 and managed1 interfaces cannot communicate with each
    other without a bridge. However, the same bridge cannot be used
    to bridge the two interfaces either (you can't read from a bridge
    that you write to as well without putting the bridge in
    promiscuous mode). Thus, we create a virtual ethernet interface
    with one peer on either bridge to allow the bridges to forward
    traffic between managed0 and managed1.
    """

    version = 1
    TIMEOUT_SECONDS = 15

    def dut_sees_bss(self, bssid):
        """
        Check if a DUT can see a BSS in scan results.

        @param bssid: string bssid of AP we expect to see in scan results.
        @return True iff scan results from DUT include the specified BSS.

        """
        runner = iw_runner.IwRunner(remote_host=self.context.client.host)
        is_requested_bss = lambda iw_bss: iw_bss.bss == bssid
        scan_results = runner.scan(self.context.client.wifi_if)
        return scan_results and filter(is_requested_bss, scan_results)


    def retry(self, func, reason, timeout_seconds=TIMEOUT_SECONDS):
        """
        Retry a function until it returns true or we time out.

        @param func: function that takes no parameters.
        @param reason: string concise description of what the function does.
        @param timeout_seconds: int number of seconds to wait for a True
                response from |func|.

        """
        logging.info('Waiting for %s.', reason)
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            if func():
                return
            time.sleep(1)
        else:
            raise error.TestFail('Timed out waiting for %s.' % reason)

    def parse_additional_arguments(self, commandline_args, additional_params):
        """Hook into super class to take control files parameters.

        @param commandline_args dict of parsed parameters from the autotest.
        @param additional_params xmlrpc_security_types security config.

        """
        self._security_config = additional_params

    def run_once(self,host):
        """Test body."""

        mac0 = '02:00:00:00:03:00'
        mac1 = '02:00:00:00:04:00'
        id0 = '020000000300'
        id1 = '020000000400'
        key0 = '0f0e0d0c0b0a09080706050403020100'
        key1 = '000102030405060708090a0b0c0d0e0f'
        mdid = 'a1b2'
        br0 = 'br0'
        br1 = 'br1'
        router0_conf = hostap_config.HostapConfig(channel=1,
                       mode=hostap_config.HostapConfig.MODE_11G,
                       security_config=self._security_config,
                       bssid=mac0,
                       mdid=mdid,
                       nas_id=id0,
                       r1kh_id=id0,
                       r0kh='%s %s %s' % (mac1, id1, key0),
                       r1kh='%s %s %s' % (mac1, mac1, key1),
                       bridge=br0)
        router1_conf = hostap_config.HostapConfig(channel=48,
                       mode=hostap_config.HostapConfig.MODE_11A,
                       security_config=self._security_config,
                       bssid=mac1,
                       mdid=mdid,
                       nas_id=id1,
                       r1kh_id=id1,
                       r0kh='%s %s %s' % (mac0, id0, key1),
                       r1kh='%s %s %s' % (mac0, mac0, key0),
                       bridge=br1)
        client_conf = xmlrpc_datatypes.AssociationParameters(
                      security_config=self._security_config)

        # Configure the inital AP.
        self.context.configure(router0_conf)
        router_ssid = self.context.router.get_ssid()

        # Connect to the inital AP.
        client_conf.ssid = router_ssid
        self.context.assert_connect_wifi(client_conf)

        # Setup a second AP with the same SSID.
        router1_conf.ssid = router_ssid
        self.context.configure(router1_conf, multi_interface=True)

        # Get BSSIDs of the two APs
        bssid0 = self.context.router.get_hostapd_mac(0)
        bssid1 = self.context.router.get_hostapd_mac(1)

        # Wait for DUT to see the second AP
        self.retry(lambda: self.dut_sees_bss(bssid1), 'DUT to see second AP')

        # Check which AP we are currently connected.
        # This is to include the case that wpa_supplicant
        # automatically roam to AP2 during the scan.
        interface = self.context.client.wifi_if
        curr_bssid = self.context.client.iw_runner.get_current_bssid(interface)
        if curr_bssid == bssid0:
            current_if = self.context.router.get_hostapd_interface(0)
            roam_to_bssid = bssid1
        else:
            current_if = self.context.router.get_hostapd_interface(1)
            roam_to_bssid = bssid0

        # Set up virtual ethernet interface so APs can talk to each other
        veth0 = 'veth0'
        veth1 = 'veth1'
        try:
            self.context.router.router.run('ip link add %s type veth peer name '
                                           '%s' % (veth0, veth1))
            self.context.router.router.run('ifconfig %s up' % veth0)
            self.context.router.router.run('ifconfig %s up' % veth1)
            self.context.router.router.run('ip link set %s master %s' %
                                           (veth0, br0))
            self.context.router.router.run('ip link set %s master %s' %
                                           (veth1, br1))
        except Exception as e:
            raise error.TestFail('veth configuration failed: %s' % e)


        # Set the tx power of the current interface
        # This should fix the tx power at 100mBm == 1dBm. It turns out that
        # set_tx_power does not actually change the signal level seen from the
        # DUT sufficiently to force a roam (It might vary from -45 to -30), so
        # this autotest takes advantage of wpa_supplicant's preference for
        # 5GHz channels.
        self.context.router.iw_runner.set_tx_power(current_if, 'fixed 100')

        # Expect that the DUT will re-connect to the new AP.
        self.context.client._wpa_cli_proxy.run_wpa_cli_cmd('scan')
        logging.info("Attempting to roam.")
        if not self.context.client.wait_for_roam(
               roam_to_bssid, timeout_seconds=self.TIMEOUT_SECONDS):
            self.context.client._wpa_cli_proxy.run_wpa_cli_cmd('scan')
            logging.info("Attempting to roam again.")
            if not self.context.client.wait_for_roam(
                   roam_to_bssid, timeout_seconds=self.TIMEOUT_SECONDS):
                raise error.TestFail('Failed to roam.')

        # Tear down
        self.context.router.router.run('ip link del %s' % veth0)
        self.context.router.deconfig()
