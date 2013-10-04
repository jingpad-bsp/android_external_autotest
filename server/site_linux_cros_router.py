# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re
import time

from autotest_lib.client.common_lib import error
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
            'force_local_server': None,
            'phy_bus_preference': {
                'monitor': 'usb',
                'managed': 'pci'
            }})
        super(LinuxCrosRouter, self).__init__(host, cros_params, test_name)


    def get_hostapd_start_command(self, log_file, pid_file, conf_file):
        return '%s -dd -B -t -f %s -P %s %s' % (
                self.cmd_hostapd, log_file, pid_file, conf_file)

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


    def _post_start_hook(self, params):
        hostapd_instance = self.hostapd_instances[-1]
        log_file = hostapd_instance['log_file']
        pid_file = hostapd_instance['pid_file']
        # Wait for confirmation that the router came up.
        pid = int(self.router.run('cat %s' % pid_file).stdout)
        logging.info('Waiting for hostapd to startup.')
        start_time = time.time()
        while time.time() - start_time < self.STARTUP_TIMEOUT_SECONDS:
            success = self.router.run(
                    'grep "Completing interface initialization" %s' % log_file,
                    ignore_status=True).exit_status == 0
            if success:
                break

            # A common failure is to request an invalid router configuration.
            # Detect this and exit early if we see it.
            bad_config = self.router.run(
                    'grep "Interface initialization failed" %s' % log_file,
                    ignore_status=True).exit_status == 0
            if bad_config:
                raise error.TestFail('hostapd failed to initialize AP '
                                     'interface.')

            if pid:
                early_exit = self.router.run('kill -0 %d' % pid,
                                             ignore_status=True).exit_status
                if early_exit:
                    raise error.TestFail('hostapd process terminated.')

            time.sleep(self.STARTUP_POLLING_INTERVAL_SECONDS)
        else:
            raise error.TestFail('Timed out while waiting for hostapd '
                                 'to start.')
