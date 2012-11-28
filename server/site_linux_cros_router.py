# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
from autotest_lib.client.common_lib import error
from autotest_lib.server import site_linux_router

def isLinuxCrosRouter(router):
    router_lsb = router.run('cat /etc/lsb-release', ignore_status=True).stdout
    return re.search('CHROMEOS_RELEASE', router_lsb)

class LinuxCrosRouter(site_linux_router.LinuxRouter):
    """
    Linux/mac80211-style WiFi Router support for WiFiTest class.

    As compared to LinuxRouter, LinuxCrosRouter is specialized for routers
    running a ChromiumOS image.
    """

    def __init__(self, host, params, defssid):
        cros_params = params.copy()
        cros_params.update({
            'cmd_ip': '/usr/local/sbin/ip',
            'cmd_hostapd': '/usr/local/sbin/hostapd',
            'cmd_hostapd_cli': '/usr/local/bin/hostapd_cli',
            'cmd_tcpdump': '/usr/local/sbin/tcpdump',
            'force_local_server': None,
            'phy_bus_preference': {
                'monitor': 'usb',
                'managed': 'pci'
            }})
        site_linux_router.LinuxRouter.__init__(self, host, cros_params, defssid)
        self.cmd_iptables = params.get('cmd_iptables', '/sbin/iptables')


    def _pre_start_hook(self, config):
        # Make sure a supplicant instance is not running.
        self.router.run('stop wpasupplicant', ignore_status=True)


    def start_dhcp_server(self):
        if len(self.local_servers) > 1:
            # for now, just bail if we have more than one interface.
            raise NotImplementedError('multiple DHCP servers in CrOS router')
        else:
            params = self.local_servers[0]

        dhcp_conf = '\n'.join([
            'port=0',  # disables DNS server
            'bind-interfaces',
            'log-dhcp',
            'dhcp-range=%s' % params['dhcp_range'].replace(' ', ','),
            'interface=%s' % params['interface'],
            'dhcp-leasefile=%s' % self.dhcpd_leases])
        self.router.run('cat <<EOF >%s\n%s\nEOF\n' %
            (self.dhcpd_conf, dhcp_conf))
        self.router.run('pkill -f dnsmasq', ignore_status=True)
        self.router.run('dnsmasq --conf-file=%s' % self.dhcpd_conf)

        # Punch hole in firewall, to allow DHCP traffic. Avoid
        # creating duplicate iptable rule instances by deleting
        # (possibly) existing instance first.
        self.router.run('%s -D INPUT -i %s -p udp --dport bootps -j ACCEPT' %
                        (self.cmd_iptables, params['interface']),
                        ignore_status=True)
        self.router.run('%s -A INPUT -i %s -p udp --dport bootps -j ACCEPT' %
                        (self.cmd_iptables, params['interface']))
