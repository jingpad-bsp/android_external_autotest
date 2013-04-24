# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from autotest_lib.client.common_lib import error

class LinuxSystem(object):
    """Superclass for test machines running Linux.

    Provides a common point for routines that use the cfg80211 userspace tools
    to manipulate the wireless stack, regardless of the role they play.
    Currently the commands shared are the init, which queries for wireless
    devices, along with start_capture and stop_capture.  More commands may
    migrate from site_linux_router as appropriate to share.

    """

    def __init__(self, host, params, role):
        # Command locations.
        self.cmd_iw = params.get('cmd_iw', '/usr/sbin/iw')
        self.cmd_ip = params.get('cmd_ip', '/usr/sbin/ip')
        self.cmd_dhcpd = params.get('cmd_dhcpd', '/usr/sbin/dhcpd')
        self.cmd_readlink = params.get('cmd_readlink', '/bin/ls -l')
        self.cmd_tcpdump = params.get('cmd_tcpdump', '/usr/sbin/tcpdump')

        self.phy_bus_preference = params.get('phy_bus_preference', {})
        self.phydev2 = params.get('phydev2', None)
        self.phydev5 = params.get('phydev5', None)

        self.capture_file = '/tmp/dump.pcap'
        self.capture_logfile = '/tmp/dump.log'
        self.capture_count = 0
        self.capture_running = False
        self.capture_channel = None

        self.host = host
        self.role = role

        setattr(self, '%s_start_capture' % role, self.start_capture)
        setattr(self, '%s_stop_capture' % role, self.stop_capture)

        self.phys_for_frequency, self.phy_bus_type = self._get_phy_info()
        self.wlanifs_in_use = []


    def _get_phy_info(self):
        """Get information about WiFi devices.

        Parse the output of 'iw list' and some of sysfs and return:

        A dict |phys_for_frequency| which maps from each frequency to a
        list of phys that support that channel.

        A dict |phy_bus_type| which maps from each phy to the bus type for
        each phy.

        @return phys_for_frequency, phy_bus_type tuple as described.

        """
        output = self.host.run('%s list' % self.cmd_iw).stdout
        re_wiphy = re.compile('Wiphy (.*)')
        re_mhz = re.compile('(\d+) MHz')
        in_phy = False
        phy_list = []
        phys_for_frequency = {}
        for line in output.splitlines():
            match_wiphy = re_wiphy.match(line)
            if match_wiphy:
                in_phy = True
                wiphyname = match_wiphy.group(1)
                phy_list.append(wiphyname)
            elif in_phy:
                if line[0] == '\t':
                    match_mhz = re_mhz.search(line)
                    if match_mhz:
                        mhz = int(match_mhz.group(1))
                        if mhz not in phys_for_frequency:
                            phys_for_frequency[mhz] = [wiphyname]
                        else:
                            phys_for_frequency[mhz].append(wiphyname)
                else:
                    in_phy = False

        phy_bus_type = {}
        for phy in phy_list:
            phybus = 'unknown'
            command = '%s /sys/class/ieee80211/%s' % (self.cmd_readlink, phy)
            devpath = self.host.run(command).stdout
            if '/usb' in devpath:
                phybus = 'usb'
            elif '/mmc' in devpath:
                phybus = 'sdio'
            elif '/pci' in devpath:
                phybus = 'pci'
            phy_bus_type[phy] = phybus

        return phys_for_frequency, phy_bus_type


    def _remove_interface(self, interface, remove_monitor):
        """Remove an interface from a WiFi device.

        @param interface string interface to remove (e.g. wlan0).
        @param remove_monitor bool True if we should also remove a monitor.

        """
        self.host.run('%s link set %s down' % (self.cmd_ip, interface))
        self.host.run('%s dev %s del' % (self.cmd_iw, interface))
        if remove_monitor:
            # Some old hostap implementations create a 'mon.<interface>' to
            # handle management frame transmit/receive.
            self.host.run('%s link set mon.%s down' % (self.cmd_ip, interface),
                          ignore_status=True)
            self.host.run('%s dev mon.%s del' % (self.cmd_iw, interface),
                      ignore_status=True)
        for phytype in self.wlanifs:
            for phy in self.wlanifs[phytype]:
                if self.wlanifs[phytype][phy] == interface:
                    self.wlanifs[phytype].pop(phy)
                    break


    def _remove_interfaces(self):
        """Remove all WiFi devices."""
        self.wlanifs = {}
        # Remove all wifi devices.
        output = self.host.run('%s dev' % self.cmd_iw).stdout
        test = re.compile('[\s]*Interface (.*)')
        for line in output.splitlines():
            m = test.match(line)
            if m:
                self._remove_interface(m.group(1), False)


    def start_capture(self, params):
        """Start a packet capture.

        @param params dict of site_wifitest parameters.

        """
        if self.capture_running:
            self.stop_capture({})

        if 'channel' in params:
            channel = int(params['channel'])
            channel_args = '%s' % channel
            for arg in ('ht20', 'ht40+', 'ht40-'):
                if arg in params:
                    channel_args = '%s %s' % (channel_args, arg.upper())
            self.capture_channel = channel
            self.channel_args = channel_args
        else:
            channel = self.capture_channel
            channel_args = self.channel_args
        self.capture_interface = self._get_wlanif(channel, 'monitor')

        self.host.run('%s dev %s set freq %s' %
            (self.cmd_iw, self.capture_interface, channel_args))

        self.host.run('%s link set %s up' % (self.cmd_ip,
                                             self.capture_interface))

        self.host.run('%s -i %s -w %s -s %s >%s 2>&1 &' %
                      (self.cmd_tcpdump,
                       self.capture_interface,
                       self.capture_file,
                       params.get('snaplen', '0'),
                       self.capture_logfile))
        self.capture_running = True


    def stop_capture(self, params):
        """Stop a packet capture.

        @param params dict of site_wifitest parameters.

        """
        if not self.capture_running:
            return
        self.host.run('pkill -INT tcpdump >/dev/null 2>&1', ignore_status=True)
        self.host.run('%s link set %s down' % (self.cmd_ip,
                                               self.capture_interface))

        self.host.get_file(self.capture_file,
                             'debug/%s_%d.pcap' %
                             (self.role, self.capture_count))
        self.capture_count += 1
        self.capture_running = False
        self._release_wlanif(self.capture_interface)


    def _get_phy_for_frequency(self, frequency, phytype):
        """Get a phy appropriate for a frequency and phytype.

        Return the most appropriate phy interface for operating on the
        frequency |frequency| in the role indicated by |phytype|.  Prefer idle
        phys to busy phys if any exist.  Secondarily, show affinity for phys
        that use the bus type associated with this phy type.

        @param frequency int WiFi frequency of phy.
        @param phytype string key of phytype registered at construction time.
        @return string name of phy to use.

        """
        phys = self.phys_for_frequency[frequency]

        busy_phys = set(phy for phy, wlanif, phytype in self.wlanifs_in_use)
        idle_phys = [phy for phy in phys if phy not in busy_phys]
        phys = idle_phys or phys

        preferred_bus = self.phy_bus_preference.get(phytype)
        preferred_phys = [phy for phy in phys
                          if self.phy_bus_type[phy] == preferred_bus]
        phys = preferred_phys or phys

        return phys[0]


    def _get_wlanif(self, frequency, phytype, mode = None):
        """Get a WiFi device that supports the given frequency, mode, and type.

        This function is used by inherited classes, so we use the single '_'
        convention rather than the '__' we usually use for non-scriptable
        commands, since these cannot be inherited by subclasses.

        We still support the old "phydevN" parameters, but this code is
        smart enough to do without it.

        @param frequency int WiFi frequency to support.
        @param phytype string type of phy (e.g. 'monitor').
        @param mode string 'a' 'b' or 'g'.
        @return string WiFi device.

        """
        if mode in ('b', 'g') and self.phydev2 is not None:
            phy = self.phydev2
        elif mode == 'a' and self.phydev5 is not None:
            phy = self.phydev5
        elif frequency in self.phys_for_frequency:
            phy = self._get_phy_for_frequency(frequency, phytype)
        else:
            raise error.TestFail('Unable to find phy for frequency %d mode %s' %
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

        wlanif = '%s%d' % (phytype, len(self.wlanifs[phytype].keys()))
        self.wlanifs[phytype][phy] = wlanif

        self.host.run('%s phy %s interface add %s type %s' %
            (self.cmd_iw, phy, wlanif, phytype))

        self.wlanifs_in_use.append((phy, wlanif, phytype))

        return wlanif


    def _release_wlanif(self, wlanif):
        """Release a device allocated throuhg _get_wlanif().

        @param wlanif string name of device to release.

        """
        for phy, wlanif_i, phytype in self.wlanifs_in_use:
            if wlanif_i == wlanif:
                 self.wlanifs_in_use.remove((phy, wlanif, phytype))
