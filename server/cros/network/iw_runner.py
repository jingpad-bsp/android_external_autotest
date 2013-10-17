# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import re
import time

HT20 = 'HT20'
HT40_ABOVE = 'HT40+'
HT40_BELOW = 'HT40-'

# Table of lookups between the output of item 'secondary channel offset:' from
# iw <device> scan to constants.

HT_TABLE = {'no secondary': HT20,
            'above': HT40_ABOVE,
            'below': HT40_BELOW}

IwBand = collections.namedtuple('Band', ['num', 'frequencies', 'mcs_indices'])
IwBss = collections.namedtuple('IwBss', ['bss', 'frequency', 'ssid', 'ht'])
IwPhy = collections.namedtuple('Phy', ['name', 'bands'])

DEFAULT_COMMAND_IW = 'iw'

class IwRunner(object):
    """Defines an interface to the 'iw' command."""


    def __init__(self, host, command_iw=DEFAULT_COMMAND_IW):
        self._host = host
        self._command_iw = command_iw


    def add_interface(self, phy, interface, interface_type):
        """
        Add an interface to a WiFi PHY.

        @param phy: string name of PHY to add an interface to.
        @param interface: string name of interface to add.
        @param interface_type: string type of interface to add (e.g. 'monitor').

        """
        self._host.run('%s phy %s interface add %s type %s' %
                       (self._command_iw, phy, interface, interface_type))


    def disconnect_station(self, interface):
        """
        Disconnect a STA from a network.

        @param interface: string name of interface to disconnect.

        """
        self._host.run('%s dev %s disconnect' % (self._command_iw, interface))


    def ibss_join(self, interface, ssid, frequency):
        """
        Join a WiFi interface to an IBSS.

        @param interface: string name of interface to join to the IBSS.
        @param ssid: string SSID of IBSS to join.
        @param frequency: int frequency of IBSS in Mhz.

        """
        self._host.run('%s dev %s ibss join %s %d' %
                       (self._command_iw, interface, ssid, frequency))


    def ibss_leave(self, interface):
        """
        Leave an IBSS.

        @param interface: string name of interface to remove from the IBSS.

        """
        self._host.run('%s dev %s ibss leave' % (self._command_iw, interface))


    def list_interfaces(self):
        """@return list of string WiFi interface names on device."""
        output = self._host.run('%s dev' % self._command_iw).stdout
        interfaces = []
        for line in output.splitlines():
            m = re.match('[\s]*Interface (.*)', line)
            if m:
                interfaces.append(m.group(1))

        return interfaces


    def list_phys(self):
        """
        List WiFi PHYs on the given host.

        @return list of IwPhy tuples.

        """
        output = self._host.run('%s list' % self._command_iw).stdout
        current_phy = None
        current_band = None
        all_phys = []
        for line in output.splitlines():
            match_phy = re.search('Wiphy (.*)', line)
            if match_phy:
                current_phy = IwPhy(name=match_phy.group(1), bands=[])
                all_phys.append(current_phy)
                continue
            match_band = re.search('Band (\d+):', line)
            if match_band:
                current_band = IwBand(num=int(match_band.group(1)),
                                      frequencies=[],
                                      mcs_indices=[])
                current_phy.bands.append(current_band)
                continue
            if not all([current_band, current_phy, line.startswith('\t')]):
                continue

            mhz_match = re.search('(\d+) MHz', line)
            if mhz_match:
                current_band.frequencies.append(int(mhz_match.group(1)))
                continue

            # re_mcs needs to match something like:
            # HT TX/RX MCS rate indexes supported: 0-15, 32
            if re.search('HT TX/RX MCS rate indexes supported: ', line):
                rate_string = line.split(':')[1].strip()
                for piece in rate_string.split(','):
                    if piece.find('-') > 0:
                        # Must be a range like '  0-15'
                        begin, end = piece.split('-')
                        for index in range(int(begin), int(end) + 1):
                            current_band.mcs_indices.append(index)
                    else:
                        # Must be a single rate like '32   '
                        current_band.mcs_indices.append(int(piece))
        return all_phys


    def remove_interface(self, interface, ignore_status=False):
        """
        Remove a WiFi interface from a PHY.

        @param interface: string name of interface (e.g. mon0)
        @param ignore_status: boolean True iff we should ignore failures
                to remove the interface.

        """
        self._host.run('%s dev %s del' % (self._command_iw, interface),
                       ignore_status=ignore_status)


    def scan(self, interface):
        """Performs a scan.

        @param interface: the interface to run the iw command against

        @returns a list of IwBss collections; None if the scan fails

        """
        command = str('%s %s scan' % (self._command_iw, interface))
        scan = self._host.run(command, ignore_status=True)
        if scan.exit_status == 240:
            # The device was busy
           return None

        bss = None
        frequency = None
        ssid = None
        ht = None

        bss_list = []

        for line in scan.stdout.splitlines():
            line = line.strip()
            if line.startswith('BSS'):
                if bss != None:
                    iwbss = IwBss(bss, frequency, ssid, ht)
                    bss_list.append(iwbss)
                    bss = frequency = ssid = ht = None
                bss = line.split()[1]
            if line.startswith('freq:'):
                frequency = int(line.split()[1])
            if line.startswith('SSID:'):
                ssid = line.split()
                if len(ssid) > 1:
                    ssid = ssid[1]
                else:
                    ssid = None
            if line.startswith('* secondary channel offset'):
                ht = HT_TABLE[line.split(':')[1].strip()]

        bss_list.append(IwBss(bss, frequency, ssid, ht))
        return bss_list


    def set_tx_power(self, interface, power):
        """
        Set the transmission power for an interface.

        @param interface: string name of interface to set Tx power on.
        @param power: string power parameter. (e.g. 'auto').

        """
        self._host.run('%s dev %s set txpower %s' %
                       (self._command_iw, interface, power))


    def set_regulatory_domain(self, domain_string):
        """
        Set the regulatory domain of the current machine.

        @param domain_string: string regulatory domain name (e.g. 'US').

        """
        self._host.run('%s reg set %s' % (self._command_iw, domain_string))


    def wait_for_scan_result(self, interface, bss=None, ssid=None,
                             timeout_seconds=30):
        """Returns a IWBSS object for a network with the given bssed or ssid.

        @param interface: which interface to run iw against
        @param bss: BSS as a string
        @param ssid: ssid as a string
        @param timeout_seconds: the amount of time to wait in seconds

        @returns a list of IwBss collections that contain the given bss or ssid

        """
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            scan_results = self.scan(interface)
            if scan_results is None:
                continue
            matching_bsses = []
            for iwbss in scan_results:
                if bss is not None and iwbss.bss != bss:
                    continue
                if ssid is not None and iwbss.ssid != ssid:
                    continue
                matching_bsses.append(iwbss)
            if len(matching_bsses) > 0:
                return matching_bsses
