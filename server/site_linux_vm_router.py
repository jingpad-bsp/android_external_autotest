# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, re, time
from autotest_lib.client.common_lib import error
from autotest_lib.server import site_linux_system
from autotest_lib.server import site_linux_router

class LinuxVMRouter(site_linux_router.LinuxRouter):
    """
    Linux/mac80211-style WiFi Router support for WiFiTest class.

    As compared to LinuxRouter, LinuxVMRouter is specialized for routers
    running a ChromiumOS image. For example, it understands the virtual
    radios provided by mac80211_hwsim, and the dnsmasq DHCP server.
    """

    def __init__(self, host, params, defssid):
        host.run("rmmod mac80211_hwsim", ignore_status=True)
        host.run("modprobe mac80211_hwsim radios=3")

        site_linux_router.LinuxRouter.__init__(self, host, params, defssid)

        self.cmd_iptables = params.get("cmd_iptables", "/sbin/iptables")

        # Override LinuxSystem's phy assignment.
        self.phy_for_frequency = {}
        phy_infos = host.run("%s list" % self.cmd_iw).stdout.splitlines()
        phy_list = \
            [phy_info.split()[1] for phy_info in phy_infos \
               if phy_info.startswith('Wiphy')]

        # In the VM case, the client runs on the same node as the router.
        # Since LinuxRouter.__init__ removes all interfaces, we need to
        # set up a device for the client. [quiche.20110823]
        client_phy = phy_list[0]
        host.run("%s phy %s interface add client0 type managed" %
                 (self.cmd_iw, client_phy))

        # Both remaining virtual devices are dual-band. Arbitrarily
        # assign one to 2.4 GHz, and the other to 5 GHz.
        self.phydev2 = self.phydev2 or phy_list[1]
        self.phydev5 = self.phydev5 or phy_list[2]


    def _pre_config_hook(self, config):
        # kludge for hostapd 0.6.9 and earlier [quiche.20110808]
        if 'wmm_enabled' in config:
            del config['wmm_enabled']


    def start_dhcp_server(self):
        if len(self.local_servers) > 1:
            # for now, just bail if we have more than one interface.
            raise NotImplementedError("multiple DHCP servers in VM")
        else:
            params = self.local_servers[0]

        dhcp_conf = '\n'.join([
            "port=0",  # disables DNS server
            "bind-interfaces",
            "log-dhcp",
            "dhcp-range=%s" % params['dhcp_range'].replace(' ', ','),
            "interface=%s" % params['interface'],
            "dhcp-leasefile=%s" % self.dhcpd_leases])
        self.router.run("cat <<EOF >%s\n%s\nEOF\n" %
            (self.dhcpd_conf, dhcp_conf))
        self.router.run("pkill -f dnsmasq", ignore_status=True)
        self.router.run("dnsmasq --conf-file=%s" % self.dhcpd_conf)

        # Punch hole in firewall, to allow DHCP traffic. Avoid
        # creating duplicate iptable rule instances by deleting
        # (possibly) existing instance first.
        self.router.run("%s -D INPUT -i %s -p udp --dport bootps -j ACCEPT" %
                        (self.cmd_iptables, params['interface']),
                        ignore_status=True)
        self.router.run("%s -A INPUT -i %s -p udp --dport bootps -j ACCEPT" %
                        (self.cmd_iptables, params['interface']))
