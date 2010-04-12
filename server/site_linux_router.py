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
        self.cmd_iw = "/usr/sbin/iw"
        self.cmd_ip = "/usr/sbin/ip"
        self.cmd_brctl = "/usr/sbin/brctl"
        self.cmd_hostapd = "/usr/sbin/hostapd"

        self.router = host
        # default to 1st available wireless nic
        if "phydev" not in params:
            output = self.router.run("%s list" % self.cmd_iw).stdout
            wifitest = re.compile("Wiphy (.*)")
            for line in output.splitlines():
                m = wifitest.match(line)
                if m:
                    self.phydev = m.group(1)
                    break
            else:
                raise Exception("No Wireless NIC detected on the device")
        else:
            self.phydev = params['phydev']

        self.hostapd_conf = "/tmp/%s.conf" % self.phydev
        self.hostapd_driver = "nl80211"
        self.phytype = None
        self.bridgeif = params.get("bridgeif", "br-lan")
        self.wlanif = "wlan0"
        self.defssid = defssid;


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
        phydev = params.get('phydev', self.phydev)
        self.router.run("%s phy %s interface add %s type %s" %
            (self.cmd_iw, phydev, self.wlanif, self.phytype))


    def destroy(self, params):
        """ Destroy a previously created device """
        self.router.run("%s dev %s del" % (self.cmd_iw, self.wlanif))


    def config(self, params):
        """ Configure the AP per test requirements """

        if self.apmode:
            # construct the hostapd.conf file and start hostapd
            hostapd_args = ["interface=%s" % self.wlanif]
            hostapd_args.append("bridge=%s" % self.bridgeif)
            hostapd_args.append("driver=%s" %
                params.get("hostapd_driver", self.hostapd_driver))
            if 'ssid' not in params:
                params['ssid'] = self.defssid
            wmm = 0
            htcaps = None
            for k, v in params.iteritems():
                if k == 'ssid':
                    hostapd_args.append("ssid=%s" % v)
                elif k == 'channel':
                    freq = int(v)
                    if freq >= 2412 and freq <= 2472:
                        chan = 1 + (freq - 2412) / 5
                    elif freq == 2484:
                        chan = 14
                    elif freq >= 4915 and freq <= 4980:
                        chan = 183 + (freq - 4915) / 5
                    elif freq >= 5035 and freq <= 5825:
                        chan = 7 + (freq - 5025) / 5
                    else:
                        chan = -1
                    hostapd_args.append("channel=%s" % chan)
                elif k == 'country':
                    hostapd_args.append("country_code=%s" % v)
                elif k == 'dotd':
                    hostapd_args.append("ieee80211d=1")
                elif k == '-dotd':
                    hostapd_args.append("ieee80211d=0")
                elif k == 'mode':
                    if v == '11a':
                        hostapd_args.append("hw_mode=a")
                    elif v == '11g':
                        hostapd_args.append("hw_mode=g")
                    elif v == '11b':
                        hostapd_args.append("hw_mode=b")
                    elif v == '11n':
                        hostapd_args.append("ieee80211n=1")
                elif k == 'bintval':
                    hostapd_args.append("beacon_int=%s" % v)
                elif k == 'dtimperiod':
                    hostapd_args.append("dtim_period=%s" % v)
                elif k == 'rtsthreshold':
                    hostapd_args.append("rts_threshold=%s" % v)
                elif k == 'fragthreshold':
                    hostapd_args.append("fragm_threshold=%s" % v)
                elif k == 'shortpreamble':
                    hostapd_args.append("preamble=1")
                elif k == 'authmode':
                    if v == 'open':
                        hostapd_args.append("auth_algs=1")
                    elif v == 'shared':
                        hostapd_args.append("auth_algs=2")
                elif k == 'hidessid':
                    hostapd_args.append("ignore_broadcast_ssid=1")
                elif k == 'wme':
                    wmm = 1;
                elif k == '-wme':
                    wmm = 0;
                elif k == 'deftxkey':
                    hostapd_args.append("wep_default_key=%s" % v)
                elif k == 'ht20':
                    htcaps.append("")
                    wmm = 1;
                elif k == 'ht40':
                    htcaps.append("[HT40-][HT40+]")
                    wmm = 1
# XXX no support                elif k == 'rifs':
                elif k == 'shortgi':
                    htcaps.append("[SHORT-GI-20][SHORT-GI-40]")
                else:
                    hostapd_args.append("%s=%s" % (k, v))

            if htcaps is not None:
                hostapd_args.append("ieee80211n=1")
                hostapd_args.append("ht_capab=%s" % htcaps)
            hostapd_args.append("wmm_enabled=%d" % wmm)

            self.router.run("cat <<EOF >%s\n%s\nEOF\n" %
                (self.hostapd_conf, "\n".join(hostapd_args)))
            self.router.run("%s -B %s" %
                (self.cmd_hostapd, self.hostapd_conf))

#        else:
#            # use iw to manually configure interface



    def deconfig(self, params):
        """ De-configure the AP (typically marks wlanif down) """

        self.router.run("%s link set %s down" % (self.cmd_ip, self.wlanif))
        if self.hostapd_conf is not None:
            self.router.run("pkill hostapd >/dev/null 2>&1")
            self.router.run("rm -f %s" % self.hostapd_conf)
            self.hostapd_conf = None


    def client_check_config(self, params):
        """
        Check network configuration on client to verify parameters
        have been negotiated during the connection to the router.
        """
        # XXX fill in
