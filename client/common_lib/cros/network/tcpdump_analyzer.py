# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import datetime
import logging
import re

from autotest_lib.client.common_lib import utils


Frame = collections.namedtuple('Frame', ['time_delta_seconds',
                                         'bit_rate',
                                         'mcs_index',
                                         'probe_ssid'])

WLAN_PROBE_FILTER = 'wlan type mgt subtype probe-req'

def get_frames(pcap_path, remote_host=None, pcap_filter='',
               command_tcpdump='tcpdump'):
    """
    Get a parsed representation of the contents of a pcap file.

    @param pcap_path: string path to pcap file.
    @param remote_host: Host object (if the file is remote).
    @param pcap_filter: string filter to apply to captured frames.
    @param command_tcpdump: string path of tcpdump command.
    @return list of Frame structs.

    """
    run = utils.run
    if remote_host:
        run = remote_host.run
    result = run('%s -n -ttttt -r %s "%s"' % (command_tcpdump, pcap_path,
                                              pcap_filter))
    frames = []
    logging.info('Parsing frames')
    bad_lines = 0
    for frame in result.stdout.splitlines():
        match = re.search(r'^(?P<ts>\d{2}:\d{2}:\d{2}\.\d{6}).* '
                          r'(?P<rate>\d+.\d) Mb/s', frame)
        if not match:
            logging.debug('Found bad tcpdump line: %s', frame)
            bad_lines += 1
            continue

        rel_time = datetime.datetime.strptime(match.group('ts'),
                                              '%H:%M:%S.%f')
        diff_seconds = rel_time.time()
        rate = float(match.group('rate'))

        match = re.search(r'MCS (\d+)', frame)
        if match:
            mcs_index = int(match.group(1))
        else:
            mcs_index = None

        # Note: this fails if the SSID contains a ')'
        match = re.search(r'Probe Request \(([^)]*)\)', frame)
        if match:
            probe_ssid = match.group(1)
        else:
            probe_ssid = None

        frames.append(Frame(diff_seconds, rate, mcs_index, probe_ssid))

    if bad_lines:
        logging.error('Failed to parse %d lines.', bad_lines)

    return frames


def get_probe_ssids(pcap_path, remote_host=None, probe_sender=None):
    """
    Get the SSIDs that were named in 802.11 probe requests frames.

    Parse a pcap, returning all the SSIDs named in 802.11 probe
    request frames. If |probe_sender| is specified, only probes
    from that MAC address will be considered.

    @param pcap_path: string path to pcap file.
    @param remote_host: Host object (if the file is remote).
    @param probe_sender: MAC address of the device sending probes.

    @return: A frozenset of the SSIDs that were probed.

    """
    if probe_sender:
        pcap_filter = '%s and wlan addr2 %s' % (
            WLAN_PROBE_FILTER, probe_sender)
    else:
        pcap_filter = WLAN_PROBE_FILTER

    frames = get_frames(pcap_path, remote_host, pcap_filter)

    return frozenset(
            [frame.probe_ssid for frame in frames
             if frame.probe_ssid is not None])
