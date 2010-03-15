# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

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
        self.router = host
        # TODO(sleffler) default to 1st available wireless nic
        self.phydev = params['phydev']
        # TODO(sleffler) default to 1st available wired nic
        self.wiredif = params['wiredev']
        self.hostapd_conf = "/tmp/%s.conf" % self.phydev
        self.phytype = None


    def __isapmode(self):
        return self.phytype is None


    def create(self, params):
        """ Create a wifi device of the specified type """
        #
        # AP mode is handled entirely by hostapd so we only
        # have to setup others (mapping the bsd type to what
        # iw wants)
        #
        # map from bsd types to iw types
        self.phytype = {
            "sta"       : "managed",
            "monitor"   : "monitor",
            "adhoc"     : "adhoc",
            "ibss"      : "ibss",
            "ap"        : None,          # NB: handled by hostapd
            "hostap"    : None,          # NB: handled by hostapd
            "mesh"      : "mesh",
            "wds"       : "wds",
        }[params['type']]
        if not __isapmode():
            phydev = params.get('phydev', self.phydev)
            self.router.run("iw phy %s interface add wlan0 type %s" %
                (phydev, self.phytype))
            self.wlanif = "wlan0"              # XXX get wlanX device name back

        self.router.run("ifconfig bridge0 create addm %s addm %s" %
            (self.wlanif, self.wiredif))
        self.bridgeif = "bridge0"


    def destroy(self, params):
        """ Destroy a previously created device """
        if not __isapmode():
            self.router.run("iw dev %s del" % self.wlanif)
        self.router.run("ifconfig %s destroy" % self.bridgeif)


    def config(self, params):
        """ Configure the AP per test requirements """

        if __isapmode():
            # construct the hostapd.conf file and start hostapd
            hostapd_args = None
            wmm = 0
            htcaps = None
            for (k, v) in params.keys():
                if k == 'channel':
                    # XXX map frequency to channe #?
                    hostapd_args.append("channel=%s" % v)
                elif k == 'country':
                    hostapd_args.append("country_code=%s\n" % v)
                elif k == 'dotd':
                    hostapd_args.append("ieee80211d=1\n")
                elif k == '-dotd':
                    hostapd_args.append("ieee80211d=0\n")
                elif k == 'mode':
                    if v == '11a':
                        hostapd_args.append("hw_mode=a\n")
                    elif v == '11g':
                        hostapd_args.append("hw_mode=g\n")
                    elif v == '11b':
                        hostapd_args.append("hw_mode=b\n")
                    elif v == '11n':
                        hostapd_args.append("ieee80211n=1\n")
                elif k == 'bintval':
                    hostapd_args.append("beacon_int=%s\n" % v)
                elif k == 'dtimperiod':
                    hostapd_args.append("dtim_period=%s\n" % v)
                elif k == 'rtsthreshold':
                    hostapd_args.append("rts_threshold=%s\n" % v)
                elif k == 'fragthreshold':
                    hostapd_args.append("fragm_threshold=%s\n" % v)
                elif k == 'shortpreamble':
                    hostapd_args.append("preamble=1\n")
                elif k == 'authmode':
                    if v == 'open':
                        hostapd_args.append("auth_algs=1\n")
                    elif v == 'shared':
                        hostapd_args.append("auth_algs=2\n")
                elif k == 'hidessid':
                    hostapd_args.append("ignore_broadcast_ssid=1\n")
                elif k == 'wme':
                    wmm = 1;
                elif k == '-wme':
                    wmm = 0;
                elif k == 'deftxkey':
                    hostapd_args.append("wep_default_key=%s\n" % v)
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
                    hostapd_args.append("%s=%s\n" % (k, v))

            if htcaps is not None:
                hostapd_args.append("ieee80211n=1\nht_capab=%s\n" % htcaps)
            hostapd_args.append("wmm_enable=%d\n" % wmm)

            self.router.run("cat <'EOF' >%s\n\
                interface=%s\n\
                bridge=%s\n\
                driver=nl80211\n\
                %s\n\
                EOF\n" % \
                (self.hostapd_conf, self.phydev, self.bridgeif, hostapd_args))
            self.router.run("hostapd -B %s" % self.hostapd_conf)
#        else:
#            # use iw to manually configure interface

        # finally bring the bridge up
        self.router.run("ifconfig %s up" % self.bridgeif)


    def deconfig(self, params):
        """ De-configure the AP (typically marks wlanif down) """

        self.router.run("ifconfig %s down" % self.wlanif)
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
