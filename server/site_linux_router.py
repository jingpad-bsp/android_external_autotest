# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import random
import re
import string

from autotest_lib.client.common_lib import base_utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import interface
from autotest_lib.server import site_linux_system
from autotest_lib.server.cros import wifi_test_utils
from autotest_lib.server.cros.network import hostap_config

def isLinuxRouter(host):
    """Check if host is a linux router.

    @param host Host object representing the remote machine.
    @return True iff remote system is a Linux system.

    """
    router_uname = host.run('uname').stdout
    return re.search('Linux', router_uname)


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

    def get_capabilities(self):
        """@return iterable object of AP capabilities for this system."""
        caps = set()
        try:
            self.cmd_send_management_frame = wifi_test_utils.must_be_installed(
                    self.router, '/usr/bin/send_management_frame')
            caps.add(self.CAPABILITY_SEND_MANAGEMENT_FRAME)
        except error.TestFail:
            pass
        return super(LinuxRouter, self).get_capabilities().union(caps)


    def __init__(self, host, params, test_name):
        """Build a LinuxRouter.

        @param host Host object representing the remote machine.
        @param params dict of settings from site_wifitest based tests.
        @param test_name string name of this test.  Used in SSID creation.

        """
        site_linux_system.LinuxSystem.__init__(self, host, params, 'router')
        self._remove_interfaces()

        # Router host.
        self.router = host

        self.cmd_dhcpd = params.get('cmd_dhcpd', '/usr/sbin/dhcpd')
        self.cmd_hostapd = wifi_test_utils.must_be_installed(
                host, params.get('cmd_hostapd', '/usr/sbin/hostapd'))
        self.cmd_hostapd_cli = wifi_test_utils.must_be_installed(
                host, params.get('cmd_hostapd_cli', '/usr/sbin/hostapd_cli'))
        self.cmd_wpa_supplicant = wifi_test_utils.must_be_installed(
                host, params.get('cmd_wpa_supplicant',
                                 '/usr/sbin/wpa_supplicant'))
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

        self.default_config = {
            'hw_mode': 'g',
            'ctrl_interface': '/tmp/hostapd-test.control',
            'logger_syslog': '-1',
            'logger_syslog_level': '0'
        }
        self.hostapd = {
            'configured': False,
            'config_file': "/tmp/hostapd-test-%s.conf",
            'log_file': "/tmp/hostapd-test-%s.log",
            'pid_file': "/tmp/hostapd-test-%s.pid",
            'log_count': 0,
            'driver': "nl80211",
            'conf': self.default_config.copy()
        }
        self.station = {
            'configured': False,
            'config_file': "/tmp/wpa-supplicant-test-%s.conf",
            'log_file': "/tmp/wpa-supplicant-test-%s.log",
            'pid_file': "/tmp/wpa-supplicant-test-%s.pid",
            'conf': {},
        }
        self.local_servers = []
        self.hostapd_instances = []
        self.force_local_server = "force_local_server" in params
        self.dhcp_low = 1
        self.dhcp_high = 128

        # Kill hostapd and dhcp server if already running.
        self.kill_hostapd()
        self.stop_dhcp_servers()

        # Place us in the US by default
        self.iw_runner.set_regulatory_domain('US')


    def close(self):
        """Close global resources held by this system."""
        self.destroy()
        super(LinuxRouter, self).close()


    def create(self, params):
        """Create a wifi device of the specified type.

        @param params dict containing the device type under key 'type'.

        """
        self.create_wifi_device(params['type'])


    def create_wifi_device(self, device_type='hostap'):
        """Create a wifi device of the specified type.

        Defaults to creating a hostap managed device.

        @param device_type string device type.

        """
        #
        # AP mode is handled entirely by hostapd so we only
        # have to setup others (mapping the bsd type to what
        # iw wants)
        #
        # map from bsd types to iw types
        self.apmode = device_type in ('ap', 'hostap')
        if not self.apmode:
            self.station['type'] = device_type
        self.phytype = {
            'sta'       : 'managed',
            'monitor'   : 'monitor',
            'adhoc'     : 'adhoc',
            'ibss'      : 'ibss',
            'ap'        : 'managed',     # NB: handled by hostapd
            'hostap'    : 'managed',     # NB: handled by hostapd
            'mesh'      : 'mesh',
            'wds'       : 'wds',
        }[device_type]


    def destroy(self, params={}):
        """Destroy a previously created device.

        @param params dict of site_wifitest parameters.

        """
        self.deconfig(params)
        self.hostapd['conf'] = self.default_config.copy()


    def has_local_server(self):
        """@return True iff this router has local servers configured."""
        return bool(self.local_servers)


    def cleanup(self, params):
        """Clean up any resources in use.

        @param params dict of site_wifitest parameters.

        """
        # For linux, this is a no-op
        pass


    def get_hostapd_start_command(self, log_file, pid_file, conf_file):
        return '%s -dd -t -P %s %s &> %s &' % (
                self.cmd_hostapd, pid_file, conf_file, log_file)


    def start_hostapd(self, conf, params):
        """Start a hostapd instance described by conf.

        @param conf dict of hostapd configuration parameters.
        @param params dict of site_wifitest parameters.

        """
        logging.info('Starting hostapd with parameters: %r', conf)
        # Figure out the correct interface.
        interface = self._get_wlanif(self.hostapd['frequency'],
                                     self.phytype,
                                     mode=conf.get('hw_mode', 'b'))

        conf_file = self.hostapd['config_file'] % interface
        log_file = self.hostapd['log_file'] % interface
        pid_file = self.hostapd['pid_file'] % interface
        conf['interface'] = interface

        # Generate hostapd.conf.
        self._pre_config_hook(conf)
        self.router.run("cat <<EOF >%s\n%s\nEOF\n" %
            (conf_file, '\n'.join(
            "%s=%s" % kv for kv in conf.iteritems())))

        # Run hostapd.
        logging.info("Starting hostapd...")
        self.router.run('rm %s' % log_file, ignore_status=True)
        self.router.run('rm %s' % pid_file, ignore_status=True)
        self._pre_start_hook(params)
        start_command = self.get_hostapd_start_command(
                log_file, pid_file, conf_file)
        self.router.run(start_command)
        self.hostapd_instances.append({
            'ssid': conf['ssid'],
            'conf_file': conf_file,
            'log_file': log_file,
            'interface': interface,
            'pid_file': pid_file,
            'config_dict': conf.copy()
        })


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
        conf = self.hostapd['conf']
        # default RTS and frag threshold to ``off''
        conf['rts_threshold'] = '2347'
        conf['fragm_threshold'] = '2346'
        conf['driver'] = self.hostapd['driver']
        conf['ssid'] = self._build_ssid('')
        return conf


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
        if multi_interface is None and (self.hostapd['configured'] or
                                        self.station['configured']):
            self.deconfig()
        # Start with the default hostapd config parameters.
        conf = self.__get_default_hostap_config()
        conf['ssid'] = (configuration.ssid or
                        self._build_ssid(configuration.ssid_suffix))
        if configuration.bssid:
            conf['bssid'] = configuration.bssid
        conf['channel'] = configuration.channel
        self.hostapd['frequency'] = configuration.frequency
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

        # TODO(wiley): Remove this multi_interface flag when the bridge router
        # class is gone.
        params = {'multi_interface': 1} if multi_interface else {}
        self.start_hostapd(conf, params)
        # Configure transmit power
        tx_power_params = {'interface': conf['interface']}
        # TODO(wiley) support for setting transmit power
        self.set_txpower(tx_power_params)
        if self.force_local_server:
            self.start_local_server(conf['interface'])
        self._post_start_hook(params)
        logging.info('AP configured.')
        self.hostapd['configured'] = True


    def hostap_config(self, params):
        """Configure the AP per test requirements.

        @param params dict of site_wifitest parameters.

        """
        # keep parameter modifications local-only
        orig_params = params
        params = params.copy()

        multi_interface = 'multi_interface' in params
        if multi_interface:
            # remove non-hostapd config item from params
            params.pop('multi_interface')
        elif self.hostapd['configured'] or self.station['configured']:
            self.deconfig()

        local_server = params.pop('local_server', False)

        conf = self.__get_default_hostap_config()
        tx_power_params = {}
        htcaps = set()

        for k, v in params.iteritems():
            if k == 'ssid':
                conf['ssid'] = v
            elif k == 'ssid_suffix':
                conf['ssid'] = self._build_ssid(v)
            elif k == 'channel':
                freq = int(v)
                self.hostapd['frequency'] = freq

                # 2.4GHz
                if freq <= 2484:
                    # Make sure hw_mode is set
                    if conf.get('hw_mode') == 'a':
                        conf['hw_mode'] = 'g'

                    # Freq = 5 * chan + 2407, except channel 14
                    if freq == 2484:
                        conf['channel'] = 14
                    else:
                        conf['channel'] = (freq - 2407) / 5
                # 5GHz
                else:
                    # Make sure hw_mode is set
                    conf['hw_mode'] = 'a'
                    # Freq = 5 * chan + 4000
                    if freq < 5000:
                        conf['channel'] = (freq - 4000) / 5
                    # Freq = 5 * chan + 5000
                    else:
                        conf['channel'] = (freq - 5000) / 5

            elif k == 'country':
                conf['country_code'] = v
            elif k == 'dotd':
                conf['ieee80211d'] = 1
            elif k == '-dotd':
                conf['ieee80211d'] = 0
            elif k == 'mode':
                if v == '11a':
                    conf['hw_mode'] = 'a'
                elif v == '11g':
                    conf['hw_mode'] = 'g'
                elif v == '11b':
                    conf['hw_mode'] = 'b'
                elif v == '11n':
                    conf['ieee80211n'] = 1
            elif k == 'bintval':
                conf['beacon_int'] = v
            elif k == 'dtimperiod':
                conf['dtim_period'] = v
            elif k == 'rtsthreshold':
                conf['rts_threshold'] = v
            elif k == 'fragthreshold':
                conf['fragm_threshold'] = v
            elif k == 'shortpreamble':
                conf['preamble'] = 1
            elif k == 'authmode':
                if v == "open":
                    conf['auth_algs'] = 1
                elif v == "shared":
                    conf['auth_algs'] = 2
            elif k == 'hidessid':
                conf['ignore_broadcast_ssid'] = 1
            elif k == 'wme':
                conf['wmm_enabled'] = 1
            elif k == '-wme':
                conf['wmm_enabled'] = 0
            elif k == 'deftxkey':
                conf['wep_default_key'] = v
            elif k == 'ht20':
                htcaps.add('')  # NB: ensure 802.11n setup below
                conf['wmm_enabled'] = 1
            elif k == 'ht40':
                htcaps.add('[HT40-]')
                htcaps.add('[HT40+]')
                conf['wmm_enabled'] = 1
            elif k in ('ht40+', 'ht40-'):
                htcaps.add('[%s]' % k.upper())
                conf['wmm_enabled'] = 1
            elif k == 'shortgi':
                htcaps.add('[SHORT-GI-20]')
                htcaps.add('[SHORT-GI-40]')
            elif k == 'pureg':
                pass        # TODO(sleffler) need hostapd support
            elif k == 'puren':
                pass        # TODO(sleffler) need hostapd support
            elif k == 'protmode':
                pass        # TODO(sleffler) need hostapd support
            elif k == 'ht':
                htcaps.add('')  # NB: ensure 802.11n setup below
            elif k == 'htprotmode':
                pass        # TODO(sleffler) need hostapd support
            elif k == 'rifs':
                pass        # TODO(sleffler) need hostapd support
            elif k == 'wepmode':
                pass        # NB: meaningless for hostapd; ignore
            elif k == '-ampdu':
                pass        # TODO(sleffler) need hostapd support
            elif k == 'txpower':
                tx_power_params['power'] = v
            else:
                conf[k] = v

        # Aggregate ht_capab.
        if htcaps:
            conf['ieee80211n'] = 1
            conf['ht_capab'] = ''.join(htcaps)

        self.start_hostapd(conf, orig_params)

        # Configure transmit power
        tx_power_params['interface'] = conf['interface']
        self.set_txpower(tx_power_params)

        if self.force_local_server or local_server is not False:
            self.start_local_server(conf['interface'])

        self._post_start_hook(orig_params)

        logging.info("AP configured.")
        self.hostapd['configured'] = True


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
        if self.station['configured'] or self.hostapd['configured']:
            self.deconfig()
        interface = self._get_wlanif(config.frequency, self.phytype,
                                     config.hw_mode)
        self.station['conf']['ssid'] = (config.ssid or
                                        self._build_ssid(config.ssid_suffix))
        # Connect the station
        self.router.run('%s link set %s up' % (self.cmd_ip, interface))
        self.iw_runner.ibss_join(
                interface, self.station['conf']['ssid'], config.frequency)
        # Always start a local server.
        self.start_local_server(interface)
        # Remember that this interface is up.
        self.station['configured'] = True
        self.station['interface'] = interface


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
        iface = interface.Interface(self.station['interface'], self.router)
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
        conf_file = self.dhcpd_conf % interface
        dhcp_conf = '\n'.join(map(
            lambda server_conf: \
                "subnet %(subnet)s netmask %(netmask)s {\n" \
                "  range %(dhcp_range)s;\n" \
                "}" % server_conf,
            self.local_servers))
        self.router.run("cat <<EOF >%s\n%s\nEOF\n" %
            (conf_file,
             '\n'.join(('ddns-update-style none;', dhcp_conf))))
        self.router.run("touch %s" % self.dhcpd_leases)

        self.router.run("pkill dhcpd >/dev/null 2>&1", ignore_status=True)
        self.router.run("%s -q -cf %s -lf %s" %
                        (self.cmd_dhcpd, conf_file, self.dhcpd_leases))


    def stop_dhcp_server(self, instance=None):
        """Stop a dhcp server on the router.

        @param instance string instance to kill.

        """
        self._kill_process_instance('dhcpd', instance, 0)


    def stop_dhcp_servers(self):
        """Stop all dhcp servers on the router."""
        self.stop_dhcp_server(None)


    def config(self, params):
        """Configure an AP based on site_wifitest parameters.

        @param params dict of site_wifitest parameters.

        """
        if self.apmode:
            self.hostap_config(params)
        else:
            config = hostap_config.HostapConfig(
                    frequency=int(params.get('channel', None)))
            self.ibss_configure(config)


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
        instance = self.hostapd_instances[ap_num]
        interface = instance['interface']
        result = self.router.run('%s addr show %s' % (self.cmd_ip, interface))
        # Example response:
        #   1: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 UP qlen 1000
        #   link/ether 99:88:77:66:55:44 brd ff:ff:ff:ff:ff:ff
        #   inet 10.0.0.1/8 brd 10.255.255.255 scope global eth0
        #   inet6 fe80::6a7f:74ff:fe66:5544/64 scope link
        # we want the MAC address after the "link/ether" above.
        parts = result.stdout.split(' ')
        return parts[parts.index('link/ether') + 1]


    def deconfig(self, params={}):
        """De-configure the AP (will also bring wlan down).

        @param params dict of parameters from site_wifitest.

        """
        self.deconfig_aps(instance=params.get('instance', None),
                          silent='silent' in params)


    def deconfig_aps(self, instance=None, silent=False):
        """De-configure an AP (will also bring wlan down).

        @param instance: int or None.  If instance is None, will bring down all
                instances of hostapd.
        @param silent: True if instances should be brought without de-authing
                the DUT.

        """
        if not self.hostapd['configured'] and not self.station['configured']:
            return

        if self.hostapd['configured']:
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
                    self._remove_interface(instance['interface'], True)

                self.kill_hostapd_instance(instance['conf_file'])
                if wifi_test_utils.is_installed(self.host,
                                                instance['log_file']):
                    self.router.get_file(instance['log_file'],
                                         'debug/hostapd_router_%d_%s.log' %
                                         (self.hostapd['log_count'],
                                          instance['interface']))
                else:
                    logging.error('Did not collect hostapd log file because '
                                  'it was missing.')
                self._release_wlanif(instance['interface'])
#               self.router.run("rm -f %(log_file)s %(conf_file)s" % instance)
            self.hostapd['log_count'] += 1
        if self.station['configured']:
            local_servers = self.local_servers
            self.local_servers = []
            if self.station['type'] == 'ibss':
                self.iw_runner.ibss_leave(self.station['interface'])
            elif self.station['type'] == 'supplicant':
                self._kill_process_instance('wpa_supplicant',
                                            self.station['interface'])
            else:
                self.iw_runner.disconnect_station(self.station['interface'])
            self.router.run("%s link set %s down" % (self.cmd_ip,
                                                     self.station['interface']))

        for server in local_servers:
            self.stop_dhcp_server(server['interface'])
            self.router.run("%s addr del %s" %
                            (self.cmd_ip, server['ip_params']),
                             ignore_status=True)

        self.hostapd['configured'] = False
        self.station['configured'] = False


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

        if not 'ssid' in self.station['conf']:
            raise error.TestFail('Requested ssid of an unconfigured AP.')

        return self.station['conf']['ssid']


    def set_txpower(self, params):
        """Set the transmission power for an interface.

        Assumes that we want to refer to the first hostapd instance unless
        'interface' is defined in params.  Sets the transmission power to
        'auto' if 'power' is not defined in params.

        @param params dict of parameters as described above.

        """
        interface = params.get('interface',
                               self.hostapd_instances[0]['interface'])
        power = params.get('power', 'auto')
        self.iw_runner.set_tx_power(interface, power)


    def deauth_client(self, client_mac):
        """Deauthenticates a client described in params.

        @param client_mac string containing the mac address of the client to be
               deauthenticated.

        """
        self.router.run('%s -p%s deauthenticate %s' %
                        (self.cmd_hostapd_cli,
                         self.hostapd['conf']['ctrl_interface'],
                         client_mac))


    @base_utils.deprecated
    def deauth(self, params):
        """Deauthenticates a client described in params.

        Deprecated: Call 'deauth_client', instead.

        @param params dict containing a key 'client'.

        """
        self.deauth_client(params['client'])


    def send_management_frame(self, frame_type, instance=0):
        """Injects a management frame into an active hostapd session.

        @param frame_type string the type of frame to send.
        @param instance int indicating which hostapd instance to inject into.

        """
        hostap_interface = self.hostapd_instances[instance]['interface']
        interface = self._get_wlanif(0, 'monitor', same_phy_as=hostap_interface)
        self.router.run("%s link set %s up" % (self.cmd_ip, interface))
        self.router.run('%s %s %s' %
                        (self.cmd_send_management_frame, interface, frame_type))
        self._release_wlanif(interface)


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

        if self.station['configured']:
            raise error.TestFail('Station is already configured.')

        client_conf = self.station['conf']
        client_conf['ssid'] = self.get_ssid(instance)

        hostap_conf = self.hostapd_instances[instance]['config_dict']
        frequency = hostap_config.HostapConfig.get_frequency_for_channel(
                hostap_conf['channel'])
        interface = self._get_wlanif(
                frequency, 'managed', hostap_conf['hw_mode'])
        client_conf['interface'] = interface

        # TODO(pstew): Configure other bits like PSK, 802.11n if tests
        # require them...
        supplicant_config = (
                'network={\n'
                '  ssid="%(ssid)s"\n'
                '  key_mgmt=NONE\n'
                '}\n' % client_conf
        )

        conf_file = self.station['config_file'] % interface
        log_file = self.station['log_file'] % interface
        pid_file = self.station['pid_file'] % interface

        self.router.run('cat <<EOF >%s\n%s\nEOF\n' %
            (conf_file, supplicant_config))

        # Connect the station.
        self.router.run('%s link set %s up' % (self.cmd_ip, interface))
        start_command = ('%s -dd -t -i%s -P%s -c%s -D%s &> %s &' %
                         (self.cmd_wpa_supplicant,
                         interface, pid_file, conf_file,
                         self.hostapd['driver'], log_file))
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

        self.station['configured'] = True
        self.station['type'] = 'supplicant'
        self.station['interface'] = interface


    def _pre_config_hook(self, config):
        """Hook for subclasses.

        Run after gathering configuration parameters,
        but before writing parameters to config file.

        @param config dict containing hostapd config parameters.

        """
        pass


    def _pre_start_hook(self, params):
        """Hook for subclasses.

        Run after generating hostapd config file, but before starting hostapd.

        @param params dict parameters from site_wifitest.

        """
        pass


    def _post_start_hook(self, params):
        """Hook for subclasses run after starting hostapd.

        @param params dict parameters from site_wifitest.

        """
        pass
