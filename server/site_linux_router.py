# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

def isLinuxRouter(router):
    router_uname = router.run('uname').stdout
    return re.search('Linux', router_uname)

class LinuxRouter(object):
    """
    Linux/mac80211-style WiFi Router support for WiFiTest class.

    This class implements test methods/steps that communicate with a
    router implemented with Linux/mac80211.  The router must
    be pre-configured to enable ssh access and have a mac80211-based
    wireless device.  We also assume hostapd 0.7.x and iw are present
    and any necessary modules are pre-loaded.
    """


    def __init__(self, host, params, defssid):
        # Command locations.
        self.cmd_iw = "/usr/sbin/iw"
        self.cmd_ip = "/usr/sbin/ip"
        self.cmd_brctl = "/usr/sbin/brctl"
        self.cmd_hostapd = "/usr/sbin/hostapd"

        # Router host.
        self.router = host

        # Network interfaces.
        self.bridgeif = params.get('bridgedev', "br-lan")
        self.wiredif = params.get('wiredev', "eth1")
        self.wlanif = "wlan0"

        # Default to 1st available wireless phy.
        if "phydev" not in params:
            output = self.router.run("%s list" % self.cmd_iw).stdout
            test = re.compile("Wiphy (.*)")
            for line in output.splitlines():
                m = test.match(line)
                if m:
                    self.phydev = m.group(1)
                    break
            else:
                raise error.TestFail("No Wireless NIC detected on the device")
        else:
            self.phydev = params['phydev']


        # hostapd configuration persists throughout the test, subsequent
        # 'config' commands only modify it.
        self.hostapd = {
            'configured': False,
            'file': "/tmp/%s.conf" % self.phydev,
            'driver': "nl80211",
            'conf': {
                'ssid': defssid,
                'interface': self.wlanif,
                'bridge': self.bridgeif,
                'hw_mode': 'g'
            }
        }

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

        # Remove all wifi devices.
        output = self.router.run("%s dev" % self.cmd_iw).stdout
        test = re.compile("[\s]*Interface (.*)")
        for line in output.splitlines():
            m = test.match(line)
            if m:
                device = m.group(1)
                self.router.run("%s link set %s down" % (self.cmd_ip, device))
                self.router.run("%s dev %s del" % (self.cmd_iw, device))

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
        if params['type'] == "ap" or params['type'] == "hostap":
            self.apmode = True
        phytype = {
            "sta"       : "managed",
            "monitor"   : "monitor",
            "adhoc"     : "adhoc",
            "ibss"      : "ibss",
            "ap"        : "managed",     # NB: handled by hostapd
            "hostap"    : "managed",     # NB: handled by hostapd
            "mesh"      : "mesh",
            "wds"       : "wds",
        }[params['type']]
        phydev = params.get('phydev', self.phydev)
        self.router.run("%s phy %s interface add %s type %s" %
            (self.cmd_iw, phydev, self.wlanif, phytype))



    def destroy(self, params):
        """ Destroy a previously created device """
        # For linux, this is the same as deconfig.
        self.deconfig(params)



    def config(self, params):
        """ Configure the AP per test requirements """

        if self.hostapd['configured']:
            self.deconfig({})

        if self.apmode:
            # Construct the hostapd.conf file and start hostapd.
            conf = self.hostapd['conf']
            htcaps = set()

            conf['driver'] = params.get('hostapd_driver',
                self.hostapd['driver'])

            for k, v in params.iteritems():
                if k == 'ssid':
                    conf['ssid'] = v
                elif k == 'channel':
                    freq = int(v)

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
                else:
                    conf[k] = v

            # Aggregate ht_capab.
            if htcaps:
                conf['ieee80211n'] = 1
                conf['ht_capab'] = ''.join(htcaps)

            # Generate hostapd.conf.
            self.router.run("cat <<EOF >%s\n%s\nEOF\n" %
                (self.hostapd['file'], '\n'.join(
                "%s=%s" % kv for kv in conf.iteritems())))

            # Run hostapd.
            self.router.run("%s -B %s" %
                (self.cmd_hostapd, self.hostapd['file']))

            # Set up the bridge.
            self.router.run("%s setfd %s %d" %
                (self.cmd_brctl, self.bridgeif, 0))
            self.router.run("%s addif %s %s" %
                (self.cmd_brctl, self.bridgeif, self.wiredif))
            self.router.run("%s link set %s up" %
                (self.cmd_ip, self.wiredif))
            self.router.run("%s link set %s up" %
                (self.cmd_ip, self.bridgeif))

#        else:
#            # use iw to manually configure interface

        self.hostapd['configured'] = True


    def deconfig(self, params):
        """ De-configure the AP (will also bring wlan and the bridge down) """

        if not self.hostapd['configured']:
            return

        # Taking down hostapd takes wlan0 and mon.wlan0 down.
        self.router.run("pkill hostapd >/dev/null 2>&1", ignore_status=True)
#        self.router.run("rm -f %s" % self.hostapd['file'])

        # Tear down the bridge.
        self.router.run("%s link set %s down" % (self.cmd_ip, self.bridgeif),
            ignore_status=True)
        self.router.run("%s delbr %s" % (self.cmd_brctl, self.bridgeif),
            ignore_status=True)

        self.hostapd['configured'] = False
