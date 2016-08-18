# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server import site_linux_system
from autotest_lib.server.cros.network import wifi_cell_test_base
from autotest_lib.server.cros.network import hostap_config
from autotest_lib.server.hosts import ssh_host

SEND_RA_SCRIPT = 'sendra.py'
INSTALL_PATH = '/usr/local/bin'
PROC_NET_SNMP6 = '/proc/net/snmp6'
MULTICAST_ADDR = '33:33:00:00:00:01'
LIFETIME_FRACTION = 6
LIFETIME = 180
INTERVAL = 2
IFACE = 'managed0'

class network_WiFi_IPv6RA(wifi_cell_test_base.WiFiCellTestBase):
    """Test that we can drop/accept various IPv6 RAs."""
    version = 1

    def _cleanup(self, client_conf):
        """Deconfigure AP and cleanup test resources.

        @param client_conf: association parameters for test.

        """
        self.context.client.shill.disconnect(client_conf.ssid)
        self.context.client.shill.delete_entries_for_ssid(client_conf.ssid)
        self.context.router.deconfig()
        self.context.capture_host.stop_capture()


    def send_ra(self, mac=MULTICAST_ADDR, interval=1, count=None, iface=IFACE,
                lifetime=LIFETIME):
        """Invoke scapy and send RA to the device.

        @param mac: string HWAddr/MAC address to send the packets to.
        @param interval: int Time to sleep between consecutive packets.
        @param count: int Number of packets to be sent.
        @param iface: string of the WiFi interface to use for sending packets.
        @param lifetime: int router lifetime in seconds.

        """
        scapy_command = os.path.join(INSTALL_PATH, SEND_RA_SCRIPT)
        options = ' -m %s -i %d -c %d -l %d -in %s' %(mac, interval, count,
                                                      lifetime, iface)
        self.context.router.host.run(scapy_command + options)


    def get_icmp6intype134(self):
        """Read the value of Icmp6InType134 and return integer.

        @return integer value >=0; raises TestError if command fails.

        """
        ra_count_str = self.context.client.host.run(
                'grep Icmp6InType134 %s' % PROC_NET_SNMP6).stdout
        if ra_count_str:
            return int(ra_count_str.split()[1])
        raise error.TestError('Failed to fetch value of Icmp6InType134')


    def run_once(self):
        """Sets up a router, connects to it, and sends RAs."""
        client_conf = xmlrpc_datatypes.AssociationParameters()
        client_mac = self.context.client.wifi_mac
        self.context.router.deconfig()
        ap_config = hostap_config.HostapConfig(channel=6,
                mode=hostap_config.HostapConfig.MODE_11G,
                ssid='OnHubWiFi_ch5_802.11g')
        self.context.configure(ap_config)
        self.context.capture_host.start_capture(2437, ht_type='HT20')
        client_conf.ssid = self.context.router.get_ssid()
        assoc_result = self.context.assert_connect_wifi(client_conf)
        self.context.client.collect_debug_info(client_conf.ssid)

        with self.context.client.assert_no_disconnects():
            self.context.assert_ping_from_dut()
        if self.context.router.detect_client_deauth(client_mac):
            raise error.TestFail(
                'Client de-authenticated during the test')

        # Sleep for 10 seconds to put the phone in WoW mode.
        time.sleep(10)

        # Copy scapy script to the AP.
        ap_name = self.context.client.host.hostname.split('.')[0] + '-router'
        ap_sshhost = ssh_host.SSHHost(hostname=ap_name)
        current_dir = os.path.dirname(os.path.realpath(__file__))
        send_ra_script = os.path.join(current_dir, SEND_RA_SCRIPT)
        ap_sshhost.send_file(send_ra_script, INSTALL_PATH)

        ra_count = self.get_icmp6intype134()
        # Start scapy to send RA to the phone's MAC
        self.send_ra(mac=client_mac, interval=0, count=1)
        ra_count_latest = self.get_icmp6intype134()

        # The phone should accept the first unique RA in sequence.
        if ra_count_latest != ra_count + 1:
            logging.debug('Device dropped the first RA in sequence')
            raise error.TestFail('Device dropped the first RA in sequence.')

        # Generate and send 'x' number of duplicate RAs, for 1/6th of the the
        # lifetime of the original RA. Test assumes that the original RA has a
        # lifetime of 180s. Hence, all RAs received within the next 30s of the
        # original RA should be filtered.
        ra_count = ra_count_latest
        count = LIFETIME / LIFETIME_FRACTION / INTERVAL
        self.send_ra(mac=client_mac, interval=INTERVAL, count=count)
        ra_count_latest = self.get_icmp6intype134()
        pkt_loss = count - (ra_count_latest - ra_count)
        percentage_loss = float(pkt_loss) / count * 100
        # Fail test if at least 90% of RAs were not dropped.
        if percentage_loss < 90:
            logging.debug('Device did not filter duplicate RAs correctly.'
                          '%d Percent of duplicate RAs were accepted' %
                          (100 - percentage_loss))
            raise error.TestFail('Device accepted a duplicate RA.')

        # Any new RA after this should be accepted.
        self.send_ra(mac=client_mac, interval=INTERVAL, count=2)
        ra_count_latest = self.get_icmp6intype134()
        if ra_count_latest != ra_count + 1:
            logging.debug('Device did not accept new RA after 1/6th time'
                          ' interval.')
            raise error.TestFail('Device dropped a valid RA in sequence.')

        self._cleanup(client_conf)
