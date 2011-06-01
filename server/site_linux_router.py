# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, re, time
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

        self.bridgeif = params.get('bridgedev', "br-lan")
        self.wiredif = params.get('wiredev', "eth0")
        self.cmd_brctl = "/usr/sbin/brctl"
        self.cmd_hostapd = "/usr/sbin/hostapd"
        self.cmd_hostapd_cli = "/usr/sbin/hostapd_cli"

        # Router host.
        self.router = host


        # hostapd configuration persists throughout the test, subsequent
        # 'config' commands only modify it.
        self.defssid = defssid
        self.hostapd = {
            'configured': False,
            'file': "/tmp/hostapd-test.conf",
            'log': "/tmp/hostapd-test.log",
            'log_count': 0,
            'driver': "nl80211",
            'conf': {
                'ssid': defssid,
                'bridge': self.bridgeif,
                'hw_mode': 'g',
                'ctrl_interface': '/tmp/hostapd-test.control'
            }
        }
        self.station = {
            'configured': False,
            'conf': {
                'ssid': defssid,
            },
            'local_server_state': None,
            'local_server': {
                'address': '192.168.3.254/24',
                'dhcp_range': (1, 128),
                'dhcpd_conf': '/tmp/dhcpd.conf',
                'lease_file': '/tmp/dhcpd.leases'
            }
        }
        self.station['local_server'].update(params.get('local_server', {}))

        # Kill hostapd if already running.
        self.router.run("pkill hostapd >/dev/null 2>&1", ignore_status=True)

        # Remove all bridges.
        output = self.router.run("%s show" % self.cmd_brctl).stdout
        test = re.compile("^(\S+).*")
        for line in output.splitlines()[1:]:
            m = test.match(line)
            if m:
                device = m.group(1)
                self.router.run("%s link set %s down" % (self.cmd_ip, device))
                self.router.run("%s delbr %s" % (self.cmd_brctl, device))

        # Place us in the US by default
        self.router.run("%s reg set US" % self.cmd_iw)


    def create(self, params):
        """ Create a wifi device of the specified type """
        #
        # AP mode is handled entirely by hostapd so we only
        # have to setup others (mapping the bsd type to what
        # iw wants)
        #
        # map from bsd types to iw types
        self.apmode = params['type'] in ("ap", "hostap")
        if not self.apmode:
            self.station['type'] = params['type']
        self.phytype = {
            "sta"       : "managed",
            "monitor"   : "monitor",
            "adhoc"     : "adhoc",
            "ibss"      : "ibss",
            "ap"        : "managed",     # NB: handled by hostapd
            "hostap"    : "managed",     # NB: handled by hostapd
            "mesh"      : "mesh",
            "wds"       : "wds",
        }[params['type']]


    def destroy(self, params):
        """ Destroy a previously created device """
        # For linux, this is the same as deconfig.
        self.deconfig(params)



    def hostap_config(self, params):
        """ Configure the AP per test requirements """

        multi_interface = 'multi_interface' in params
        if multi_interface:
            params.pop('multi_interface')
        elif self.hostapd['configured'] or self.station['configured']:
            self.deconfig({})

        # Construct the hostapd.conf file and start hostapd.
        conf = self.hostapd['conf']
        tx_power_params = {}
        htcaps = set()

        conf['driver'] = params.get('hostapd_driver',
            self.hostapd['driver'])

        for k, v in params.iteritems():
            if k == 'ssid':
                conf['ssid'] = v
            elif k == 'ssid_suffix':
                conf['ssid'] = self.defssid + v
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

        # Figure out the correct interface.
        conf['interface'] = self._get_wlanif(self.hostapd['frequency'],
                                             self.phytype,
                                             mode=conf.get('hw_mode', 'b'))

        # Generate hostapd.conf.
        self.router.run("cat <<EOF >%s\n%s\nEOF\n" %
            (self.hostapd['file'], '\n'.join(
            "%s=%s" % kv for kv in conf.iteritems())))

        if not multi_interface:
            logging.info("Initializing bridge...")
            self.router.run("%s addbr %s" %
                            (self.cmd_brctl, self.bridgeif))
            self.router.run("%s setfd %s %d" %
                            (self.cmd_brctl, self.bridgeif, 0))
            self.router.run("%s stp %s %d" %
                            (self.cmd_brctl, self.bridgeif, 0))

        # Run hostapd.
        logging.info("Starting hostapd...")
        self.router.run("%s -dd %s > %s &" %
            (self.cmd_hostapd, self.hostapd['file'], self.hostapd['log']))


        # Set up the bridge.
        if not multi_interface:
            logging.info("Setting up the bridge...")
            self.router.run("%s addif %s %s" %
                            (self.cmd_brctl, self.bridgeif, self.wiredif))
            self.router.run("%s link set %s up" %
                            (self.cmd_ip, self.wiredif))
            self.router.run("%s link set %s up" %
                            (self.cmd_ip, self.bridgeif))
            self.hostapd['interface'] = conf['interface']
        else:
            tx_power_params['interface'] = conf['interface']

        # Configure transmit power
        self.set_txpower(tx_power_params)

        logging.info("AP configured.")

        self.hostapd['configured'] = True


    def station_local_addr(self, idx):
        """
        Simple IPv4 calculator.  Takes host address in "IP/bits" notation
        and returns netmask, broadcast address as well as integer offsets
        into the address range.
        """
        addr_str,bits = self.station['local_server_state']['address'].split('/')
        addr = map(int, addr_str.split('.'))
        mask_bits = (-1 << (32-int(bits))) & 0xffffffff
        mask = [(mask_bits >> s) & 0xff for s in range(24, -1, -8)]
        if idx == 'netmask':
            return '.'.join(map(str, mask))
        elif idx == 'broadcast':
            offset = [m ^ 0xff for m in mask]
        else:
            offset = [(idx >> s) & 0xff for s in range(24, -1, -8)]
        return '.'.join(map(str, [(a & m) + o
                                  for a, m, o in zip(addr, mask, offset)]))


    def station_config(self, params):
        multi_interface = 'multi_interface' in params
        if multi_interface:
            params.pop('multi_interface')
        elif self.station['configured'] or self.hostapd['configured']:
            self.deconfig({})

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

        if not multi_interface:
            logging.info("Initializing bridge...")
            self.router.run("%s addbr %s" %
                            (self.cmd_brctl, self.bridgeif))
            self.router.run("%s setfd %s %d" %
                            (self.cmd_brctl, self.bridgeif, 0))
            self.router.run("%s stp %s %d" %
                            (self.cmd_brctl, self.bridgeif, 0))

        # Run interface configuration commands
        for k, v in conf.iteritems():
            if k != 'ssid':
                self.router.run("%s dev %s set %s %s" %
                                (self.cmd_iw, interface, k, v))

        # Connect the station
        self.router.run("%s link set %s up" % (self.cmd_ip, interface))
        connect_cmd = ('ibss join' if self.station['type'] == 'ibss'
                       else 'connect')
        self.router.run("%s dev %s %s %s %d" %
                        (self.cmd_iw, interface, connect_cmd,
                         conf['ssid'], freq))

        if self.station['type'] != 'ibss':
            # Add wireless interface to the bridge
            self.router.run("%s addif %s %s" %
                            (self.cmd_brctl, self.bridgeif, interface))

            # Add wired interface to the bridge, then bring up the bridge if
            if not multi_interface:
                logging.info("Setting up the bridge...")
                self.router.run("%s addif %s %s" %
                                (self.cmd_brctl, self.bridgeif, self.wiredif))
                self.router.run("%s link set %s up" %
                                (self.cmd_ip, self.wiredif))
                self.router.run("%s link set %s up" %
                                (self.cmd_ip, self.bridgeif))

        if local_server is not False:
            logging.info("Starting up local server...")
            params = self.station['local_server'].copy()
            params.update(local_server or {})
            self.station['local_server_state'] = params
            params['subnet'] = self.station_local_addr(0)
            params['netmask'] = self.station_local_addr('netmask')
            params['dhcp_range'] = ' '.join(map(self.station_local_addr,
                                                params['dhcp_range']))

            params['ip_params'] = ("%s broadcast %s dev %s" %
                                   (params['address'],
                                    self.station_local_addr('broadcast'),
                                    interface))
            self.router.run("%s addr add %s" %
                            (self.cmd_ip, params['ip_params']))
            self.router.run("%s link set %s up" %
                            (self.cmd_ip, interface))

            self.router.run("cat <<EOF >%s\n%s\nEOF\n" %
                (params['dhcpd_conf'],
                 '\n'.join(('ddns-update-style none;',
                            'subnet %(subnet)s netmask %(netmask)s {',
                            '   range %(dhcp_range)s;', '}')) % params))
            self.router.run("pkill dhcpd >/dev/null 2>&1", ignore_status=True)
            self.router.run("%s -q -cf %s -lf %s %s" %
                            (self.cmd_dhcpd, params['dhcpd_conf'],
                             params['lease_file'], interface))

        self.station['configured'] = True
        self.station['interface'] = interface


    def config(self, params):
        if self.apmode:
            self.hostap_config(params)
        else:
            self.station_config(params)


    def deconfig(self, params):
        """ De-configure the AP (will also bring wlan and the bridge down) """

        if not self.hostapd['configured'] and not self.station['configured']:
            return

        # Taking down hostapd takes wlan0 and mon.wlan0 down.
        if self.hostapd['configured']:
            if 'silent' in params:
                # Deconfigure without notifying DUT.  Remove the monitor
                # interface hostapd uses to send beacon and DEAUTH packets
                self._remove_interfaces()

            self.router.run("pkill hostapd >/dev/null 2>&1", ignore_status=True)
#           self.router.run("rm -f %s" % self.hostapd['file'])
            self.router.get_file(self.hostapd['log'],
                                 'debug/hostapd_router_%d.log' %
                                 self.hostapd['log_count'])
            self.hostapd['log_count'] += 1
        if self.station['configured']:
            if self.station['type'] == 'ibss':
                self.router.run("%s dev %s ibss leave" %
                                (self.cmd_iw, self.station['interface']))
            else:
                self.router.run("%s dev %s disconnect" %
                                (self.cmd_iw, self.station['interface']))
            self.router.run("%s link set %s down" % (self.cmd_ip,
                                                     self.station['interface']))
            if self.station['local_server_state']:
                self.router.run("pkill dhcpd >/dev/null 2>&1",
                                ignore_status=True)
                self.router.run("%s addr del %s" %
                                (self.cmd_ip, self.station
                                 ['local_server_state']['ip_params']))
                self.station['local_server_state'] = None

        # Try a couple times to remove the bridge; hostapd may still be exiting
        for attempt in range(3):
            self.router.run("%s link set %s down" %
                            (self.cmd_ip, self.bridgeif), ignore_status=True)

            result = self.router.run("%s delbr %s" %
                                     (self.cmd_brctl, self.bridgeif),
                                     ignore_status=True)
            if not result.stderr or 'No such device' in result.stderr:
                break
            time.sleep(1)
        else:
            raise error.TestFail("Unable to delete bridge %s: %s" %
                                 (self.bridgeif, result.stderr))


        self.hostapd['configured'] = False
        self.station['configured'] = False


    def get_ssid(self):
        return self.hostapd['conf']['ssid']


    def set_txpower(self, params):
        self.router.run("%s dev %s set txpower %s" %
                        (self.cmd_iw, params.get('interface',
                                                 self.hostapd['interface']),
                         params.get('power', 'auto')))


    def deauth(self, params):
        self.router.run('%s -p%s deauthenticate %s' %
                        (self.cmd_hostapd_cli,
                         self.hostapd['conf']['ctrl_interface'],
                         params['client']))
