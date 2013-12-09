# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging
import re
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils


HT20 = 'HT20'
HT40_ABOVE = 'HT40+'
HT40_BELOW = 'HT40-'

SECURITY_OPEN = 'open'
SECURITY_WEP = 'wep'
SECURITY_WPA = 'wpa'
SECURITY_WPA2 = 'wpa2'
# MIxed mode security is WPA2/WPA
SECURITY_MIXED = 'mixed'

# Table of lookups between the output of item 'secondary channel offset:' from
# iw <device> scan to constants.

HT_TABLE = {'no secondary': HT20,
            'above': HT40_ABOVE,
            'below': HT40_BELOW}

IwBand = collections.namedtuple('Band', ['num', 'frequencies', 'mcs_indices'])
IwBss = collections.namedtuple('IwBss', ['bss', 'frequency', 'ssid', 'security',
                                         'ht'])
# The fields for IwPhy are as follows:
#   name: string name of the phy, such as "phy0"
#   bands: list of IwBand objects.
#   modes: List of strings containing interface modes supported, such as "AP".
#   command: List of strings containing nl80211 commands supported, such as
#          "authenticate".
IwPhy = collections.namedtuple('Phy', ['name', 'bands', 'modes', 'commands'])

DEFAULT_COMMAND_IW = 'iw'

IW_LINK_KEY_BEACON_INTERVAL = 'beacon int'
IW_LINK_KEY_DTIM_PERIOD = 'dtim period'
IW_LINK_KEY_FREQUENCY = 'freq'


class IwRunner(object):
    """Defines an interface to the 'iw' command."""


    def __init__(self, remote_host=None, command_iw=DEFAULT_COMMAND_IW):
        self._run = utils.run
        if remote_host:
            self._run = remote_host.run
        self._command_iw = command_iw


    def add_interface(self, phy, interface, interface_type):
        """
        Add an interface to a WiFi PHY.

        @param phy: string name of PHY to add an interface to.
        @param interface: string name of interface to add.
        @param interface_type: string type of interface to add (e.g. 'monitor').

        """
        self._run('%s phy %s interface add %s type %s' %
                  (self._command_iw, phy, interface, interface_type))


    def disconnect_station(self, interface):
        """
        Disconnect a STA from a network.

        @param interface: string name of interface to disconnect.

        """
        self._run('%s dev %s disconnect' % (self._command_iw, interface))


    def get_link_value(self, interface, iw_link_key, ignore_failures=False):
        """Get the value of a link property for |interface|.

        This command parses fields of iw link:

        #> iw dev wlan0 link
        Connected to 74:e5:43:10:4f:c0 (on wlan0)
              SSID: PMKSACaching_4m9p5_ch1
              freq: 5220
              RX: 5370 bytes (37 packets)
              TX: 3604 bytes (15 packets)
              signal: -59 dBm
              tx bitrate: 13.0 MBit/s MCS 1

              bss flags:      short-slot-time
              dtim period:    5
              beacon int:     100

        @param iw_link_key: string one of IW_LINK_KEY_* defined above.
        @param interface: string desired value of iw link property.

        """
        result = self._run('%s dev %s link' % (self._command_iw, interface),
                           ignore_status=ignore_failures)
        if result.exit_status:
            # When roaming, there is a period of time for mac80211 based drivers
            # when the driver is 'associated' with an SSID but not a particular
            # BSS.  This causes iw to return an error code (-2) when attempting
            # to retrieve information specific to the BSS.  This does not happen
            # in mwifiex drivers.
            return None

        find_re = re.compile('\s*%s:\s*(.*\S)\s*$' % iw_link_key)
        find_results = filter(bool,
                              map(find_re.match, result.stdout.splitlines()))
        if not find_results:
            if ignore_failures:
                return None

            raise error.TestFail('Could not find iw link property %s.' %
                                 iw_link_key)

        actual_value = find_results[0].group(1)
        logging.info('Found iw link key %s with value %s.',
                     iw_link_key, actual_value)
        return actual_value


    def ibss_join(self, interface, ssid, frequency):
        """
        Join a WiFi interface to an IBSS.

        @param interface: string name of interface to join to the IBSS.
        @param ssid: string SSID of IBSS to join.
        @param frequency: int frequency of IBSS in Mhz.

        """
        self._run('%s dev %s ibss join %s %d' %
                  (self._command_iw, interface, ssid, frequency))


    def ibss_leave(self, interface):
        """
        Leave an IBSS.

        @param interface: string name of interface to remove from the IBSS.

        """
        self._run('%s dev %s ibss leave' % (self._command_iw, interface))


    def list_interfaces(self):
        """@return list of string WiFi interface names on device."""
        output = self._run('%s dev' % self._command_iw).stdout
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
        output = self._run('%s list' % self._command_iw).stdout
        current_phy = None
        current_band = None
        current_section = None
        all_phys = []
        for line in output.splitlines():
            match_phy = re.search('Wiphy (.*)', line)
            if match_phy:
                current_phy = IwPhy(name=match_phy.group(1), bands=[], modes=[],
                                    commands=[])
                all_phys.append(current_phy)
                continue

            match_section = re.match('\s*(\w.*):', line)
            if match_section:
                current_section = match_section.group(1)
                match_band = re.match('Band (\d+)', current_section)
                if match_band:
                    current_band = IwBand(num=int(match_band.group(1)),
                                          frequencies=[],
                                          mcs_indices=[])
                    current_phy.bands.append(current_band)
                continue

            if current_section == 'Supported interface modes' and current_phy:
                mode_match = re.search('\* (\w+)', line)
                if mode_match:
                    current_phy.modes.append(mode_match.group(1))
                    continue

            if current_section == 'Supported commands' and current_phy:
                command_match = re.search('\* (\w+)', line)
                if command_match:
                    current_phy.commands.append(command_match.group(1))
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
        self._run('%s dev %s del' % (self._command_iw, interface),
                  ignore_status=ignore_status)


    def determine_security(self, supported_securities):
        """Determines security from the given list of supported securities.

        @param supported_securities: list of supported securities from scan

        """
        if not supported_securities:
            security = SECURITY_OPEN
        elif len(supported_securities) == 1:
            security = supported_securities[0]
        else:
            security = SECURITY_MIXED
        return security


    def scan(self, interface, frequencies=(), ssids=()):
        """Performs a scan.

        @param interface: the interface to run the iw command against
        @param frequencies: list of int frequencies in Mhz to scan.
        @param ssids: list of string SSIDs to send probe requests for.

        @returns a list of IwBss collections; None if the scan fails

        """
        freq_param = ''
        if frequencies:
            freq_param = ' freq %s' % ' '.join(map(str, frequencies))
        ssid_param = ''
        if ssids:
           ssid_param = ' ssid "%s"' % '" "'.join(ssids)

        command = str('%s dev %s scan%s%s' % (self._command_iw, interface,
                                              freq_param, ssid_param))
        scan = self._run(command, ignore_status=True)
        if scan.exit_status != 0:
            # The device was busy
           return None

        bss = None
        frequency = None
        ssid = None
        ht = None
        security = None

        supported_securities = []
        bss_list = []

        for line in scan.stdout.splitlines():
            line = line.strip()
            if line.startswith('BSS'):
                if bss != None:
                    security = self.determine_security(supported_securities)
                    iwbss = IwBss(bss, frequency, ssid, security, ht)
                    bss_list.append(iwbss)
                    bss = frequency = ssid = security = ht = None
                    supported_securities = []
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
            if line.startswith('WPA'):
               supported_securities.append(SECURITY_WPA)
            if line.startswith('RSN'):
               supported_securities.append(SECURITY_WPA2)
        security = self.determine_security(supported_securities)
        bss_list.append(IwBss(bss, frequency, ssid, security, ht))
        return bss_list


    def set_tx_power(self, interface, power):
        """
        Set the transmission power for an interface.

        @param interface: string name of interface to set Tx power on.
        @param power: string power parameter. (e.g. 'auto').

        """
        self._run('%s dev %s set txpower %s' %
                  (self._command_iw, interface, power))


    def set_regulatory_domain(self, domain_string):
        """
        Set the regulatory domain of the current machine.

        @param domain_string: string regulatory domain name (e.g. 'US').

        """
        self._run('%s reg set %s' % (self._command_iw, domain_string))


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
                time.sleep(5) ## allow in-progress scan to complete
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


    def wait_for_link(self, interface, timeout_seconds=10):
        """Waits until a link completes on |interface|.

        @param interface: which interface to run iw against.
        @param timeout_seconds: the amount of time to wait in seconds.

        @returns True if link was established before the timeout.

        """
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            link_results = self._run('%s dev %s link' %
                                     (self._command_iw, interface))
            if 'Not connected' not in link_results.stdout:
                return True
            time.sleep(1)
        return False
