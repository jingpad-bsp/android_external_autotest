# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import time

HT20 = 'HT20'
HT40_ABOVE = 'HT40+'
HT40_BELOW = 'HT40-'

# Table of lookups between the output of item 'secondary channel offset:' from
# iw <device> scan to constants.

HT_TABLE = {'no secondary': HT20,
            'above': HT40_ABOVE,
            'below': HT40_BELOW}

IwBss = collections.namedtuple('IwBss', ['bss', 'frequency', 'ssid', 'ht'])

DEFAULT_COMMAND_IW = 'iw'

class IwRunner(object):
    """Class that parses iw <device>."""


    def __init__(self, host, iw_command=DEFAULT_COMMAND_IW):
        self._host = host
        self._iw_command = iw_command


    def scan(self, interface):
        """Performs a scan.

        @param interface: the interface to run the iw command against

        @returns a list of IwBss collections; None if the scan fails

        """
        command = str('%s %s scan' % (self._iw_command, interface))
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
