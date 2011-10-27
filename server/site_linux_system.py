# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re, logging
from autotest_lib.client.common_lib import error

class LinuxSystem(object):
    """ This is a superclass for test machines running Linux.  It provides
        a common point for routines that use the cfg80211 users space tools
        to manipulate the wireless stack, regardless of the role they play.
        Currently the commands shared are the init, which queries for wireless
        devices, along with start_capture and stop_capture.  More commands
        may migrate from site_linux_router as appropriate to share.
    """
    def __init__(self, host, params, role):
        # Command locations.
        self.cmd_iw = params.get("cmd_iw", "/usr/sbin/iw")
        self.cmd_ip = params.get("cmd_ip", "/usr/sbin/ip")
        self.cmd_dhcpd = params.get("cmd_dhcpd", "/usr/sbin/dhcpd")
        self.cmd_tcpdump = params.get("cmd_tcpdump", "/usr/sbin/tcpdump")

        self.capture_file = "/tmp/dump.pcap"
        self.capture_logfile = "/tmp/dump.log"
        self.capture_count = 0
        self.capture_running = False
        self.capture_channel = None

        self.host = host
        self.role = role

        setattr(self, '%s_start_capture' % role, self.start_capture)
        setattr(self, '%s_stop_capture' % role, self.stop_capture)

        # Network interfaces.
        self.phy_for_frequency = {}

        # Parse the output of 'iw phy' and find a device for each frequency
        output = host.run("%s list" % self.cmd_iw).stdout
        re_wiphy = re.compile("Wiphy (.*)")
        re_mhz = re.compile("(\d+) MHz")
        in_phy = False
        for line in output.splitlines():
            match_wiphy = re_wiphy.match(line)
            if match_wiphy:
                in_phy = True
                wiphyname = match_wiphy.group(1)
            elif in_phy:
                if line[0] == '\t':
                    match_mhz = re_mhz.search(line)
                    if match_mhz:
                        mhz = int(match_mhz.group(1))
                        self.phy_for_frequency[mhz] = wiphyname
                else:
                    in_phy = False
        self.phydev2 = params.get('phydev2', None)
        self.phydev5 = params.get('phydev5', None)


    def _remove_interfaces(self):
        self.wlanifs = {}
        # Remove all wifi devices.
        output = self.host.run("%s dev" % self.cmd_iw).stdout
        test = re.compile("[\s]*Interface (.*)")
        for line in output.splitlines():
            m = test.match(line)
            if m:
                device = m.group(1)
                self.host.run("%s link set %s down" % (self.cmd_ip, device))
                self.host.run("%s dev %s del" % (self.cmd_iw, device))


    def start_capture(self, params):
        if self.capture_running:
            self.stop_capture({})

        if 'channel' in params:
            channel = int(params['channel'])
            channel_args = "%s" % channel
            for arg in ('ht20', 'ht40+', 'ht40-'):
                if arg in params:
                    channel_args = "%s %s" % (channel_args, arg.upper())
            self.capture_channel = channel
            self.channel_args = channel_args
        else:
            channel = self.capture_channel
            channel_args = self.channel_args
        self.capture_interface = self._get_wlanif(channel, "monitor")

        self.host.run("%s dev %s set freq %s" %
            (self.cmd_iw, self.capture_interface, channel_args))

        self.host.run("%s link set %s up" % (self.cmd_ip,
                                             self.capture_interface))

        self.host.run("%s -i %s -w %s -s %s >%s 2>&1 &" %
                      (self.cmd_tcpdump,
                       self.capture_interface,
                       self.capture_file,
                       params.get('snaplen', '152'),
                       self.capture_logfile))
        self.capture_running = True


    def stop_capture(self, params):
        if not self.capture_running:
            return
        self.host.run("pkill -INT tcpdump >/dev/null 2>&1", ignore_status=True)
        self.host.run("%s link set %s down" % (self.cmd_ip,
                                               self.capture_interface))

        self.host.get_file(self.capture_file,
                             'debug/%s_%d.pcap' %
                             (self.role, self.capture_count))
        self.capture_count += 1
        self.capture_running = False


    def _get_wlanif(self, frequency, phytype, mode = None):
        """ This function is used by inherited classes, so we use the
            single '_' convention rather than the '__' we usually use for
            non-scriptable commands, since these cannot be inherited by
            subclasses.

            We still support the old "phydevN" parameters, but
            this code is smart enough to do without it.
        """
        if mode in ('b', 'g') and self.phydev2 is not None:
            phy = self.phydev2
        elif mode == 'a' and self.phydev5 is not None:
            phy = self.phydev5
        elif frequency in self.phy_for_frequency:
            phy = self.phy_for_frequency[frequency]
        else:
            raise error.TestFail("Unable to find phy for frequency %d mode %s" %
                                 (frequency, mode))

        # If self.wlanifs is not defined, this is the first time we've
        # allocated a wlan interface.  Perform init by calling
        # remove_interfaces().
        if not hasattr(self, 'wlanifs'):
            self._remove_interfaces()
        if phytype not in self.wlanifs:
            self.wlanifs[phytype] = {}
        elif phy in self.wlanifs[phytype]:
            return self.wlanifs[phytype][phy]

        wlanif = "%s%d" % (phytype, len(self.wlanifs[phytype].keys()))
        self.wlanifs[phytype][phy] = wlanif

        self.host.run("%s phy %s interface add %s type %s" %
            (self.cmd_iw, phy, wlanif, phytype))

        return wlanif
