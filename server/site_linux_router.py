# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging
import random
import string
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import interface
from autotest_lib.server import site_linux_system
from autotest_lib.server.cros import wifi_test_utils
from autotest_lib.server.cros.network import hostap_config


StationInstance = collections.namedtuple('StationInstance',
                                         ['ssid', 'interface', 'dev_type'])


class LinuxRouter(site_linux_system.LinuxSystem):
    """Linux/mac80211-style WiFi Router support for WiFiTest class.

    This class implements test methods/steps that communicate with a
    router implemented with Linux/mac80211.  The router must
    be pre-configured to enable ssh access and have a mac80211-based
    wireless device.  We also assume hostapd 0.7.x and iw are present
    and any necessary modules are pre-loaded.

    """

    KNOWN_TEST_PREFIX = 'network_WiFi'
    STARTUP_POLLING_INTERVAL_SECONDS = 0.5
    STARTUP_TIMEOUT_SECONDS = 10
    SUFFIX_LETTERS = string.ascii_lowercase + string.digits
    SUBNET_PREFIX_OCTETS = (192, 168)

    HOSTAPD_CONF_FILE_PATTERN = '/tmp/hostapd-test-%s.conf'
    HOSTAPD_LOG_FILE_PATTERN = '/tmp/hostapd-test-%s.log'
    HOSTAPD_PID_FILE_PATTERN = '/tmp/hostapd-test-%s.pid'
    HOSTAPD_CONTROL_INTERFACE_PATTERN = '/tmp/hostapd-test-%s.ctrl'
    HOSTAPD_DRIVER_NAME = 'nl80211'

    STATION_CONF_FILE_PATTERN = '/tmp/wpa-supplicant-test-%s.conf'
    STATION_LOG_FILE_PATTERN = '/tmp/wpa-supplicant-test-%s.log'
    STATION_PID_FILE_PATTERN = '/tmp/wpa-supplicant-test-%s.pid'

    def get_capabilities(self):
        """@return iterable object of AP capabilities for this system."""
        caps = set([self.CAPABILITY_IBSS])
        try:
            self.cmd_send_management_frame = wifi_test_utils.must_be_installed(
                    self.host, '/usr/bin/send_management_frame')
            caps.add(self.CAPABILITY_SEND_MANAGEMENT_FRAME)
        except error.TestFail:
            pass
        return super(LinuxRouter, self).get_capabilities().union(caps)


    @property
    def router(self):
        """Deprecated.  Use self.host instead.

        @return Host object representing the remote router.

        """
        return self.host


    def __init__(self, host, test_name):
        """Build a LinuxRouter.

        @param host Host object representing the remote machine.
        @param test_name string name of this test.  Used in SSID creation.

        """
        super(LinuxRouter, self).__init__(host, 'router')

        self.cmd_dhcpd = '/usr/sbin/dhcpd'
        self.cmd_hostapd = wifi_test_utils.must_be_installed(
                host, '/usr/sbin/hostapd')
        self.cmd_hostapd_cli = wifi_test_utils.must_be_installed(
                host, '/usr/sbin/hostapd_cli')
        self.cmd_wpa_supplicant = wifi_test_utils.must_be_installed(
                host, '/usr/sbin/wpa_supplicant')
        self.dhcpd_conf = '/tmp/dhcpd.%s.conf'
        self.dhcpd_leases = '/tmp/dhcpd.leases'

        # hostapd configuration persists throughout the test, subsequent
        # 'config' commands only modify it.
        self.ssid_prefix = test_name
        if self.ssid_prefix.startswith(self.KNOWN_TEST_PREFIX):
            # Many of our tests start with an uninteresting prefix.
            # Remove it so we can have more unique bytes.
            self.ssid_prefix = self.ssid_prefix[len(self.KNOWN_TEST_PREFIX):]
        self.ssid_prefix = self.ssid_prefix.lstrip('_')
        self.ssid_prefix += '_'

        self._total_hostapd_instances = 0
        self.local_servers = []
        self.hostapd_instances = []
        self.station_instances = []
        self.dhcp_low = 1
        self.dhcp_high = 128

        # Kill hostapd and dhcp server if already running.
        self.kill_hostapd()
        self.stop_dhcp_servers()

        # Place us in the US by default
        self.iw_runner.set_regulatory_domain('US')


    def close(self):
        """Close global resources held by this system."""
        self.deconfig()
        super(LinuxRouter, self).close()


    def has_local_server(self):
        """@return True iff this router has local servers configured."""
        return bool(self.local_servers)


    def start_hostapd(self, hostapd_conf_dict, configuration):
        """Start a hostapd instance described by conf.

        @param hostapd_conf_dict dict of hostapd configuration parameters.
        @param configuration HostapConfig object.

        """
        logging.info('Starting hostapd with parameters: %r',
                     hostapd_conf_dict)
        # Figure out the correct interface.
        interface = self.get_wlanif(configuration.frequency, 'managed')

        conf_file = self.HOSTAPD_CONF_FILE_PATTERN % interface
        log_file = self.HOSTAPD_LOG_FILE_PATTERN % interface
        pid_file = self.HOSTAPD_PID_FILE_PATTERN % interface
        control_interface = self.HOSTAPD_CONTROL_INTERFACE_PATTERN % interface
        hostapd_conf_dict['interface'] = interface
        hostapd_conf_dict['ctrl_interface'] = control_interface

        # Generate hostapd.conf.
        self.router.run("cat <<EOF >%s\n%s\nEOF\n" %
            (conf_file, '\n'.join(
            "%s=%s" % kv for kv in hostapd_conf_dict.iteritems())))

        # Run hostapd.
        logging.info("Starting hostapd...")
        self.router.run('rm %s' % log_file, ignore_status=True)
        self.router.run('rm %s' % pid_file, ignore_status=True)
        self.router.run('stop wpasupplicant', ignore_status=True)
        start_command = '%s -dd -B -t -f %s -P %s %s' % (
                self.cmd_hostapd, log_file, pid_file, conf_file)
        self.router.run(start_command)
        self.hostapd_instances.append({
            'ssid': hostapd_conf_dict['ssid'],
            'conf_file': conf_file,
            'log_file': log_file,
            'interface': interface,
            'pid_file': pid_file,
            'config_dict': hostapd_conf_dict.copy()
        })

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

            # A common failure is an invalid router configuration.
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


    def _kill_process_instance(self, process, instance=None, wait=0):
        """Kill a process on the router.

        Kills program named |process|, optionally only a specific
        |instance|.  If |wait| is specified, we makes sure |process| exits
        before returning.

        @param process string name of process to kill.
        @param instance string instance of process to kill.
        @param wait int timeout in seconds to wait for.

        """
        if instance:
            search_arg = '-f "%s.*%s"' % (process, instance)
        else:
            search_arg = process

        cmd = "pkill %s >/dev/null 2>&1" % search_arg

        if wait:
            cmd += (" && while pgrep %s &> /dev/null; do sleep 1; done" %
                    search_arg)
            self.router.run(cmd, timeout=wait, ignore_status=True)
        else:
            self.router.run(cmd, ignore_status=True)


    def kill_hostapd_instance(self, instance):
        """Kills a hostapd instance.

        @param instance string instance to kill.

        """
        self._kill_process_instance('hostapd', instance, 30)


    def kill_hostapd(self):
        """Kill all hostapd instances."""
        self.kill_hostapd_instance(None)


    def __get_default_hostap_config(self):
        """@return dict of default options for hostapd."""
        return {'hw_mode': 'g',
                'logger_syslog': '-1',
                'logger_syslog_level': '0',
                # default RTS and frag threshold to ``off''
                'rts_threshold': '2347',
                'fragm_threshold': '2346',
                'driver': self.HOSTAPD_DRIVER_NAME,
                'ssid': self._build_ssid('') }


    def _build_ssid(self, suffix):
        unique_salt = ''.join([random.choice(self.SUFFIX_LETTERS)
                               for x in range(5)])
        return (self.ssid_prefix + unique_salt + suffix)[-32:]


    def hostap_configure(self, configuration, multi_interface=None):
        """Build up a hostapd configuration file and start hostapd.

        Also setup a local server if this router supports them.

        @param configuration HosetapConfig object.
        @param multi_interface bool True iff multiple interfaces allowed.

        """
        if multi_interface is None and (self.hostapd_instances or
                                        self.station_instances):
            self.deconfig()
        # Start with the default hostapd config parameters.
        conf = self.__get_default_hostap_config()
        conf['ssid'] = (configuration.ssid or
                        self._build_ssid(configuration.ssid_suffix))
        if configuration.bssid:
            conf['bssid'] = configuration.bssid
        conf['channel'] = configuration.channel
        conf['hw_mode'] = configuration.hw_mode
        if configuration.hide_ssid:
            conf['ignore_broadcast_ssid'] = 1
        if configuration.is_11n:
            conf['ieee80211n'] = 1
            conf['ht_capab'] = configuration.hostapd_ht_capabilities
        if configuration.wmm_enabled:
            conf['wmm_enabled'] = 1
        if configuration.require_ht:
            conf['require_ht'] = 1
        if configuration.beacon_interval:
            conf['beacon_int'] = configuration.beacon_interval
        if configuration.dtim_period:
            conf['dtim_period'] = configuration.dtim_period
        if configuration.frag_threshold:
            conf['fragm_threshold'] = configuration.frag_threshold
        if configuration.pmf_support:
            conf['ieee80211w'] = configuration.pmf_support
        if configuration.obss_interval:
            conf['obss_interval'] = configuration.obss_interval
        conf.update(configuration.get_security_hostapd_conf())
        self.start_hostapd(conf, configuration)
        interface = self.hostapd_instances[-1]['interface']
        self.iw_runner.set_tx_power(interface, 'auto')
        self.start_local_server(interface)
        logging.info('AP configured.')


    @staticmethod
    def ip_addr(netblock, idx):
        """Simple IPv4 calculator.

        Takes host address in "IP/bits" notation and returns netmask, broadcast
        address as well as integer offsets into the address range.

        @param netblock string host address in "IP/bits" notation.
        @param idx string describing what to return.
        @return string containing something you hopefully requested.

        """
        addr_str,bits = netblock.split('/')
        addr = map(int, addr_str.split('.'))
        mask_bits = (-1 << (32-int(bits))) & 0xffffffff
        mask = [(mask_bits >> s) & 0xff for s in range(24, -1, -8)]
        if idx == 'local':
            return addr_str
        elif idx == 'netmask':
            return '.'.join(map(str, mask))
        elif idx == 'broadcast':
            offset = [m ^ 0xff for m in mask]
        else:
            offset = [(idx >> s) & 0xff for s in range(24, -1, -8)]
        return '.'.join(map(str, [(a & m) + o
                                  for a, m, o in zip(addr, mask, offset)]))


    def ibss_configure(self, config):
        """Configure a station based AP in IBSS mode.

        Extract relevant configuration objects from |config| despite not
        actually being a hostap managed endpoint.

        @param config HostapConfig object.

        """
        if self.station_instances or self.hostapd_instances:
            self.deconfig()
        interface = self.get_wlanif(config.frequency, 'ibss')
        ssid = (config.ssid or self._build_ssid(config.ssid_suffix))
        # Connect the station
        self.router.run('%s link set %s up' % (self.cmd_ip, interface))
        self.iw_runner.ibss_join(interface, ssid, config.frequency)
        # Always start a local server.
        self.start_local_server(interface)
        # Remember that this interface is up.
        self.station_instances.append(
                StationInstance(ssid=ssid, interface=interface,
                                dev_type='ibss'))


    def local_server_address(self, index):
        """Get the local server address for an interface.

        When we multiple local servers, we give them static IP addresses
        like 192.168.*.254.

        @param index int describing which local server this is for.

        """
        return '%d.%d.%d.%d' % (self.SUBNET_PREFIX_OCTETS + (index, 254))


    def local_peer_ip_address(self, index):
        """Get the IP address allocated for the peer associated to the AP.

        This address is assigned to a locally associated peer device that
        is created for the DUT to perform connectivity tests with.
        When we have multiple local servers, we give them static IP addresses
        like 192.168.*.253.

        @param index int describing which local server this is for.

        """
        return '%d.%d.%d.%d' % (self.SUBNET_PREFIX_OCTETS + (index, 253))


    def local_peer_mac_address(self):
        """Get the MAC address of the peer interface.

        @return string MAC address of the peer interface.

        """
        iface = interface.Interface(self.station_instances[0].interface,
                                    self.router)
        return iface.mac_address


    def start_local_server(self, interface):
        """Start a local server on an interface.

        @param interface string (e.g. wlan0)

        """
        logging.info("Starting up local server...")

        if len(self.local_servers) >= 256:
            raise error.TestFail('Exhausted available local servers')

        netblock = '%s/24' % self.local_server_address(len(self.local_servers))

        params = {}
        params['netblock'] = netblock
        params['subnet'] = self.ip_addr(netblock, 0)
        params['netmask'] = self.ip_addr(netblock, 'netmask')
        params['dhcp_range'] = ' '.join(
            (self.ip_addr(netblock, self.dhcp_low),
             self.ip_addr(netblock, self.dhcp_high)))
        params['interface'] = interface

        params['ip_params'] = ("%s broadcast %s dev %s" %
                               (netblock,
                                self.ip_addr(netblock, 'broadcast'),
                                interface))
        self.local_servers.append(params)

        self.router.run("%s addr flush %s" %
                        (self.cmd_ip, interface))
        self.router.run("%s addr add %s" %
                        (self.cmd_ip, params['ip_params']))
        self.router.run("%s link set %s up" %
                        (self.cmd_ip, interface))
        self.start_dhcp_server(interface)


    def start_dhcp_server(self, interface):
        """Start a dhcp server on an interface.

        @param interface string (e.g. wlan0)

        """
        for server in self.local_servers:
            if server['interface'] == interface:
                params = server
                break
        else:
            raise error.TestFail('Could not find local server '
                                 'to match interface: %r' % interface)

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


    def stop_dhcp_server(self, instance=None):
        """Stop a dhcp server on the router.

        @param instance string instance to kill.

        """
        self._kill_process_instance('dnsmasq', instance, 0)


    def stop_dhcp_servers(self):
        """Stop all dhcp servers on the router."""
        self.stop_dhcp_server(None)


    def get_wifi_channel(self, ap_num):
        """Return channel of BSS corresponding to |ap_num|.

        @param ap_num int which BSS to get the channel of.
        @return int primary channel of BSS.

        """
        instance = self.hostapd_instances[ap_num]
        return instance['config_dict']['channel']


    def get_wifi_ip(self, ap_num):
        """Return IP address on the WiFi subnet of a local server on the router.

        If no local servers are configured (e.g. for an RSPro), a TestFail will
        be raised.

        @param ap_num int which local server to get an address from.

        """
        if self.local_servers:
            return self.ip_addr(self.local_servers[ap_num]['netblock'],
                                'local')
        else:
            raise error.TestFail("No IP address assigned")


    def get_hostapd_mac(self, ap_num):
        """Return the MAC address of an AP in the test.

        @param ap_num int index of local server to read the MAC address from.
        @return string MAC address like 00:11:22:33:44:55.

        """
        if not self.local_servers:
            raise error.TestFail('Cannot retrieve MAC: '
                                 'no AP instances configured.')

        instance = self.hostapd_instances[ap_num]
        ap_interface = interface.Interface(instance['interface'], self.host)
        return ap_interface.mac_address


    def deconfig(self):
        """A legacy, deprecated alias for deconfig_aps."""
        self.deconfig_aps()


    def deconfig_aps(self, instance=None, silent=False):
        """De-configure an AP (will also bring wlan down).

        @param instance: int or None.  If instance is None, will bring down all
                instances of hostapd.
        @param silent: True if instances should be brought without de-authing
                the DUT.

        """
        if not self.hostapd_instances and not self.station_instances:
            return

        if self.hostapd_instances:
            local_servers = []
            if instance is not None:
                instances = [ self.hostapd_instances.pop(instance) ]
                for server in self.local_servers:
                    if server['interface'] == instances[0]['interface']:
                        local_servers = [server]
                        self.local_servers.remove(server)
                        break
            else:
                instances = self.hostapd_instances
                self.hostapd_instances = []
                local_servers = self.local_servers
                self.local_servers = []

            for instance in instances:
                if silent:
                    # Deconfigure without notifying DUT.  Remove the interface
                    # hostapd uses to send beacon and DEAUTH packets.
                    self.remove_interface(instance['interface'])

                self.kill_hostapd_instance(instance['conf_file'])
                if wifi_test_utils.is_installed(self.host,
                                                instance['log_file']):
                    self.router.get_file(instance['log_file'],
                                         'debug/hostapd_router_%d_%s.log' %
                                         (self._total_hostapd_instances,
                                          instance['interface']))
                else:
                    logging.error('Did not collect hostapd log file because '
                                  'it was missing.')
                self.release_interface(instance['interface'])
#               self.router.run("rm -f %(log_file)s %(conf_file)s" % instance)
            self._total_hostapd_instances += 1
        if self.station_instances:
            local_servers = self.local_servers
            self.local_servers = []
            instance = self.station_instances.pop()
            if instance.dev_type == 'ibss':
                self.iw_runner.ibss_leave(instance.interface)
            elif instance.dev_type == 'managed':
                self._kill_process_instance('wpa_supplicant',
                                            instance.interface)
            else:
                self.iw_runner.disconnect_station(instance.interface)
            self.router.run('%s link set %s down' %
                            (self.cmd_ip, instance.interface))

        for server in local_servers:
            self.stop_dhcp_server(server['interface'])
            self.router.run("%s addr del %s" %
                            (self.cmd_ip, server['ip_params']),
                             ignore_status=True)


    def confirm_pmksa_cache_use(self, instance=0):
        """Verify that the PMKSA auth was cached on a hostapd instance.

        @param instance int router instance number.

        """
        log_file = self.hostapd_instances[instance]['log_file']
        pmksa_match = 'PMK from PMKSA cache'
        result = self.router.run('grep -q "%s" %s' % (pmksa_match, log_file),
                                 ignore_status=True)
        if result.exit_status:
            raise error.TestFail('PMKSA cache was not used in roaming.')


    def get_ssid(self, instance=None):
        """@return string ssid for the network stemming from this router."""
        if instance is None:
            instance = 0
            if len(self.hostapd_instances) > 1:
                raise error.TestFail('No instance of hostapd specified with '
                                     'multiple instances present.')

        if self.hostapd_instances:
            return self.hostapd_instances[instance]['ssid']

        if self.station_instances:
            return self.station_instances[0].ssid

        raise error.TestFail('Requested ssid of an unconfigured AP.')


    def deauth_client(self, client_mac):
        """Deauthenticates a client described in params.

        @param client_mac string containing the mac address of the client to be
               deauthenticated.

        """
        control_if = self.hostapd_instances[-1]['config_dict']['ctrl_interface']
        self.router.run('%s -p%s deauthenticate %s' %
                        (self.cmd_hostapd_cli, control_if, client_mac))


    def send_management_frame(self, frame_type, instance=0):
        """Injects a management frame into an active hostapd session.

        @param frame_type string the type of frame to send.
        @param instance int indicating which hostapd instance to inject into.

        """
        hostap_interface = self.hostapd_instances[instance]['interface']
        interface = self.get_wlanif(0, 'monitor', same_phy_as=hostap_interface)
        self.router.run("%s link set %s up" % (self.cmd_ip, interface))
        self.router.run('%s %s %s' %
                        (self.cmd_send_management_frame, interface, frame_type))
        self.release_interface(interface)


    def detect_client_deauth(self, client_mac, instance=0):
        """Detects whether hostapd has logged a deauthentication from
        |client_mac|.

        @param client_mac string the MAC address of the client to detect.
        @param instance int indicating which hostapd instance to query.

        """
        interface = self.hostapd_instances[instance]['interface']
        deauth_msg = "%s: deauthentication: STA=%s" % (interface, client_mac)
        log_file = self.hostapd_instances[instance]['log_file']
        result = self.router.run("grep -qi '%s' %s" % (deauth_msg, log_file),
                                 ignore_status=True)
        return result.exit_status == 0


    def detect_client_coexistence_report(self, client_mac, instance=0):
        """Detects whether hostapd has logged an action frame from
        |client_mac| indicating information about 20/40MHz BSS coexistence.

        @param client_mac string the MAC address of the client to detect.
        @param instance int indicating which hostapd instance to query.

        """
        coex_msg = ('nl80211: MLME event frame - hexdump(len=.*): '
                    '.. .. .. .. .. .. .. .. .. .. %s '
                    '.. .. .. .. .. .. .. .. 04 00.*48 01 ..' %
                    ' '.join(client_mac.split(':')))
        log_file = self.hostapd_instances[instance]['log_file']
        result = self.router.run("grep -qi '%s' %s" % (coex_msg, log_file),
                                 ignore_status=True)
        return result.exit_status == 0


    def add_connected_peer(self, instance=0):
        """Configure a station connected to a running AP instance.

        Extract relevant configuration objects from the hostap
        configuration for |instance| and generate a wpa_supplicant
        instance that connects to it.  This allows the DUT to interact
        with a client entity that is also connected to the same AP.  A
        full wpa_supplicant instance is necessary here (instead of just
        using the "iw" command to connect) since we want to enable
        advanced features such as TDLS.

        @param instance int indicating which hostapd instance to connect to.

        """
        if not self.hostapd_instances:
            raise error.TestFail('Hostapd is not configured.')

        if self.station_instances:
            raise error.TestFail('Station is already configured.')

        ssid = self.get_ssid(instance)
        hostap_conf = self.hostapd_instances[instance]['config_dict']
        frequency = hostap_config.HostapConfig.get_frequency_for_channel(
                hostap_conf['channel'])
        interface = self.get_wlanif(frequency, 'managed')

        # TODO(pstew): Configure other bits like PSK, 802.11n if tests
        # require them...
        supplicant_config = (
                'network={\n'
                '  ssid="%(ssid)s"\n'
                '  key_mgmt=NONE\n'
                '}\n' % {'ssid': ssid}
        )

        conf_file = self.STATION_CONF_FILE_PATTERN % interface
        log_file = self.STATION_LOG_FILE_PATTERN % interface
        pid_file = self.STATION_PID_FILE_PATTERN % interface

        self.router.run('cat <<EOF >%s\n%s\nEOF\n' %
            (conf_file, supplicant_config))

        # Connect the station.
        self.router.run('%s link set %s up' % (self.cmd_ip, interface))
        start_command = ('%s -dd -t -i%s -P%s -c%s -D%s &> %s &' %
                         (self.cmd_wpa_supplicant,
                         interface, pid_file, conf_file,
                         self.HOSTAPD_DRIVER_NAME, log_file))
        self.router.run(start_command)
        self.iw_runner.wait_for_link(interface)

        # Assign an IP address to this interface.
        self.router.run('%s addr add %s/24 dev %s' %
                        (self.cmd_ip, self.local_peer_ip_address(instance),
                         interface))

        # Since we now have two network interfaces connected to the same
        # network, we need to disable the kernel's protection against
        # incoming packets to an "unexpected" interface.
        self.router.run('echo 2 > /proc/sys/net/ipv4/conf/%s/rp_filter' %
                        interface)

        # Similarly, we'd like to prevent the hostap interface from
        # replying to ARP requests for the peer IP address and vice
        # versa.
        self.router.run('echo 1 > /proc/sys/net/ipv4/conf/%s/arp_ignore' %
                        interface)
        self.router.run('echo 1 > /proc/sys/net/ipv4/conf/%s/arp_ignore' %
                        hostap_conf['interface'])

        self.station_instances.append(
                StationInstance(ssid=ssid, interface=interface,
                                dev_type='managed'))
