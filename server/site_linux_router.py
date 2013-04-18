# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re

from autotest_lib.client.common_lib import error
from autotest_lib.server import site_linux_system

def isLinuxRouter(router):
    router_uname = router.run('uname').stdout
    return re.search('Linux', router_uname)

class LinuxRouter(site_linux_system.LinuxSystem):
    """
    Linux/mac80211-style WiFi Router support for WiFiTest class.

    This class implements test methods/steps that communicate with a
    router implemented with Linux/mac80211.  The router must
    be pre-configured to enable ssh access and have a mac80211-based
    wireless device.  We also assume hostapd 0.7.x and iw are present
    and any necessary modules are pre-loaded.
    """


    def __init__(self, host, params, defssid):
        site_linux_system.LinuxSystem.__init__(self, host, params, "router")
        self._remove_interfaces()

        # Router host.
        self.router = host

        self.cmd_hostapd = self.__must_be_installed(host,
            params.get("cmd_hostapd", "/usr/sbin/hostapd"))
        self.cmd_hostapd_cli = \
            params.get("cmd_hostapd_cli", "/usr/sbin/hostapd_cli")
        self.dhcpd_conf = "/tmp/dhcpd.%s.conf"
        self.dhcpd_leases = "/tmp/dhcpd.leases"

        # hostapd configuration persists throughout the test, subsequent
        # 'config' commands only modify it.
        self.defssid = defssid
        self.default_config = {
            'ssid': defssid,
            'hw_mode': 'g',
            'ctrl_interface': '/tmp/hostapd-test.control',
            'logger_syslog': '-1',
            'logger_syslog_level': '0'
        }
        self.hostapd = {
            'configured': False,
            'config_file': "/tmp/hostapd-test-%s.conf",
            'log_file': "/tmp/hostapd-test-%s.log",
            'log_count': 0,
            'driver': "nl80211",
            'conf': self.default_config.copy()
        }
        self.station = {
            'configured': False,
            'conf': {
                'ssid': defssid,
            },
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
        self.router.run("%s reg set US" % self.cmd_iw)

    def __must_be_installed(self, host, cmd):
        if not self.__is_installed(host, cmd):
            raise error.TestFail('Unable to find %s on %s' % (cmd, host.ip))
        return cmd

    def __is_installed(self, host, filename):
        result = host.run("ls %s" % filename, ignore_status=True)
        m = re.search(filename, result.stdout)
        return m is not None


    def create(self, params):
        """
        Create a wifi device of the specified type.

        @param params dict containing the device type under key 'type'.

        """
        self.create_wifi_device(params['type'])


    def create_wifi_device(self, device_type='hostap'):
        """
        Create a wifi device of the specified type.

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
        """ Destroy a previously created device """
        self.deconfig(params)
        self.hostapd['conf'] = self.default_config.copy()

    def has_local_server(self):
        return bool(self.local_servers)

    def cleanup(self, params):
        """ Clean up any resources in use """
        # For linux, this is a no-op
        pass

    def start_hostapd(self, conf, params):
        # Figure out the correct interface.
        interface = self._get_wlanif(self.hostapd['frequency'],
                                     self.phytype,
                                     mode=conf.get('hw_mode', 'b'))

        conf_file = self.hostapd['config_file'] % interface
        log_file = self.hostapd['log_file'] % interface
        conf['interface'] = interface

        # Generate hostapd.conf.
        self._pre_config_hook(conf)
        self.router.run("cat <<EOF >%s\n%s\nEOF\n" %
            (conf_file, '\n'.join(
            "%s=%s" % kv for kv in conf.iteritems())))

        # Run hostapd.
        logging.info("Starting hostapd...")
        self._pre_start_hook(params)
        self.router.run("%s -dd %s &> %s &" %
            (self.cmd_hostapd, conf_file, log_file))

        self.hostapd_instances.append({
            'conf_file': conf_file,
            'log_file': log_file,
            'interface': interface
        })

    def _kill_process_instance(self, process, instance=None, wait=0):
        """
        Kills program named |process|, optionally only a specific
        |instance|.  If |wait| is specified, we makes sure |process| exits
        before returning.
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
        self._kill_process_instance('hostapd', instance, 30)

    def kill_hostapd(self):
        self.kill_hostapd_instance(None)

    def hostap_config(self, params):
        """ Configure the AP per test requirements """

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

        # Construct the hostapd.conf file and start hostapd.
        conf = self.hostapd['conf']
        # default RTS and frag threshold to ``off''
        conf['rts_threshold'] = '2347'
        conf['fragm_threshold'] = '2346'

        tx_power_params = {}
        htcaps = set()

        conf['driver'] = params.get('hostapd_driver',
            self.hostapd['driver'])

        for k, v in params.iteritems():
            if k == 'ssid':
                conf['ssid'] = v
            elif k == 'ssid_suffix':
                conf['ssid'] = self.defssid[:(32-len(v))] + v
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
        """
        Simple IPv4 calculator.  Takes host address in "IP/bits" notation
        and returns netmask, broadcast address as well as integer offsets
        into the address range.
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


    def station_config(self, params):
        # keep parameter modifications local-only
        orig_params = params
        params = params.copy()

        if 'multi_interface' in params:
            raise NotImplementedError("station with multi_interface")

        if self.station['type'] != 'ibss':
            raise NotImplementedError("non-ibss station")

        if self.station['configured'] or self.hostapd['configured']:
            self.deconfig()

        local_server = params.pop('local_server', False)
        mode = None
        conf = self.station['conf']
        for k, v in params.iteritems():
            if k == 'ssid_suffix':
                conf['ssid'] = self.defssid + v
            elif k == 'channel':
                freq = int(v)
                if freq > 2484:
                    mode = 'a'
            elif k == 'mode':
                if v == '11a':
                    mode = 'a'
            else:
                conf[k] = v

        interface = self._get_wlanif(freq, self.phytype, mode)

        # Run interface configuration commands
        for k, v in conf.iteritems():
            if k != 'ssid':
                self.router.run("%s dev %s set %s %s" %
                                (self.cmd_iw, interface, k, v))

        # Connect the station
        self.router.run("%s link set %s up" % (self.cmd_ip, interface))
        self.router.run("%s dev %s ibss join %s %d" %
                        (self.cmd_iw, interface, conf['ssid'], freq))

        if self.force_local_server or local_server is not False:
            self.start_local_server(interface)

        self.station['configured'] = True
        self.station['interface'] = interface


    def local_server_address(self, index):
        return '%d.%d.%d.%d' % (192, 168, index, 254)

    def start_local_server(self, interface):
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
        self._kill_process_instance('dhcpd', instance, 0)

    def stop_dhcp_servers(self):
        self.stop_dhcp_server(None)


    def config(self, params):
        if self.apmode:
            self.hostap_config(params)
        else:
            self.station_config(params)


    def get_wifi_ip(self, ap_num):
        if self.local_servers:
            return self.ip_addr(self.local_servers[ap_num]['netblock'],
                                'local')
        else:
            raise error.TestFail("No IP address assigned")


    def get_hostapd_mac(self, ap_num):
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
        """ De-configure the AP (will also bring wlan down) """

        if not self.hostapd['configured'] and not self.station['configured']:
            return

        if self.hostapd['configured']:
            local_servers = []
            if 'instance' in params:
                instances = [ self.hostapd_instances.pop(params['instance']) ]
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
                if 'silent' in params:
                    # Deconfigure without notifying DUT.  Remove the interface
                    # hostapd uses to send beacon and DEAUTH packets.
                    self._remove_interface(instance['interface'], True)

                self.kill_hostapd_instance(instance['conf_file'])
                self.router.get_file(instance['log_file'],
                                     'debug/hostapd_router_%d_%s.log' %
                                     (self.hostapd['log_count'],
                                      instance['interface']))
                self._release_wlanif(instance['interface'])
#               self.router.run("rm -f %(log_file)s %(conf_file)s" % instance)
            self.hostapd['log_count'] += 1
        if self.station['configured']:
            local_servers = self.local_servers
            self.local_servers = []
            if self.station['type'] == 'ibss':
                self.router.run("%s dev %s ibss leave" %
                                (self.cmd_iw, self.station['interface']))
            else:
                self.router.run("%s dev %s disconnect" %
                                (self.cmd_iw, self.station['interface']))
            self.router.run("%s link set %s down" % (self.cmd_ip,
                                                     self.station['interface']))

        for server in local_servers:
            self.stop_dhcp_server(server['interface'])
            self.router.run("%s addr del %s" %
                            (self.cmd_ip, server['ip_params']),
                             ignore_status=True)

        self.hostapd['configured'] = False
        self.station['configured'] = False


    def verify_pmksa_auth(self, params):
        instance_num = params.get('instance', 0)
        instance = self.hostapd_instances[instance_num]
        pmksa_match = 'PMK from PMKSA cache - skip IEEE 802.1X.EAP'
        self.router.run('grep -q "%s" %s' % (pmksa_match, instance['log_file']))


    def get_ssid(self):
        return self.hostapd['conf']['ssid']


    def set_txpower(self, params):
        interface = params.get('interface',
                               self.hostapd_instances[0]['interface'])
        power = params.get('power', 'auto')
        self.router.run("%s dev %s set txpower %s" %
                        (self.cmd_iw, interface, power))


    def deauth(self, params):
        self.router.run('%s -p%s deauthenticate %s' %
                        (self.cmd_hostapd_cli,
                         self.hostapd['conf']['ctrl_interface'],
                         params['client']))


    def _pre_config_hook(self, config):
        """
        Hook for subclasses. Run after gathering configuration parameters,
        but before writing parameters to config file.
        """
        pass


    def _pre_start_hook(self, params):
        """
        Hook for subclasses. Run after generating hostapd config file, but
        before starting hostapd.
        """
        pass


    def _post_start_hook(self, params):
        """Hook for subclasses. Run after starting hostapd."""
        pass
