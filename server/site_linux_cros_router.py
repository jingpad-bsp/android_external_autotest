# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
from autotest_lib.server import site_linux_router

def isLinuxCrosRouter(router):
    """Detect if a remote system is a CrOS router (stumpy cell).

    @param router Host object representing the router.
    @return True iff |router| is a host running CrOS.

    """
    router_lsb = router.run('cat /etc/lsb-release', ignore_status=True).stdout
    return re.search('CHROMEOS_RELEASE', router_lsb)

class LinuxCrosRouter(site_linux_router.LinuxRouter):
    """
    Linux/mac80211-style WiFi Router support for WiFiTest class.

    As compared to LinuxRouter, LinuxCrosRouter is specialized for routers
    running a ChromiumOS image.
    """

    def get_capabilities(self):
        """@return iterable object of AP capabilities for this system."""
        return super(LinuxCrosRouter, self).get_capabilities().union(
                [self.CAPABILITY_IBSS])


    def __init__(self, host, params, test_name):
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
        super(LinuxCrosRouter, self).__init__(host, cros_params, test_name)
        self.cmd_iptables = params.get('cmd_iptables', '/sbin/iptables')


    def _pre_start_hook(self, config):
        # Make sure a supplicant instance is not running.
        self.router.run('stop wpasupplicant', ignore_status=True)


    def start_dhcp_server(self, interface):
        for server in self.local_servers:
            if server['interface'] == interface:
                params = server
                break
        else:
            raise RunTimeError('Could not find local server to match interface')

        dhcpd_conf_file = self.dhcpd_conf % interface
        dhcp_conf = '\n'.join([
            'port=0',  # disables DNS server
            'bind-interfaces',
            'log-dhcp',
            'dhcp-range=%s' % params['dhcp_range'].replace(' ', ','),
            'interface=%s' % params['interface'],
            'dhcp-leasefile=%s' % self.dhcpd_leases])
        self.router.run('cat <<EOF >%s\n%s\nEOF\n' %
            (dhcpd_conf_file, dhcp_conf))
        self.router.run('dnsmasq --conf-file=%s' % dhcpd_conf_file)


    def stop_dhcp_server(self, instance):
        self._kill_process_instance('dnsmasq', instance, 0)
