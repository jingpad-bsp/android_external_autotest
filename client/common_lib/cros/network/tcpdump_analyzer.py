# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import re

from autotest_lib.client.common_lib import utils

WLAN_PROBE_FILTER = 'wlan type mgt subtype probe-req'

class Frame(object):
    """A frame from a packet capture."""
    TIME_FORMAT = "%H:%M:%S.%f"

    def __init__(self, frametime, bit_rate, mcs_index, probe_ssid):
        self._datetime = frametime
        self._bit_rate = bit_rate
        self._mcs_index = mcs_index
        self._probe_ssid = probe_ssid


    @property
    def time_datetime(self):
        """The time of the frame, as a |datetime| object."""
        return self._datetime


    @property
    def bit_rate(self):
        """The bitrate used to transmit the frame, as an int."""
        return self._bit_rate


    @property
    def mcs_index(self):
        """
        The MCS index used to transmit the frame, as an int.

        The value may be None, if the frame was not transmitted
        using 802.11n modes.
        """
        return self._mcs_index


    @property
    def probe_ssid(self):
        """
        The SSID of the probe request, as a string.

        The value may be None, if the frame is not a probe request.
        """
        return self._probe_ssid


    @property
    def time_string(self):
        """The time of the frame, in local time, as a string."""
        return self._datetime.strftime(self.TIME_FORMAT)


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
    result = run('%s -n -tt -r %s "%s"' % (command_tcpdump, pcap_path,
                                           pcap_filter))
    frames = []
    logging.info('Parsing frames')
    bad_lines = 0
    for frame in result.stdout.splitlines():
        match = re.search(r'^(?P<ts>\d+\.\d{6}).* '
                          r'(?P<rate>\d+.\d) Mb/s', frame)
        if not match:
            logging.debug('Found bad tcpdump line: %s', frame)
            bad_lines += 1
            continue

        frame_datetime = datetime.datetime.fromtimestamp(
            float(match.group('ts')))
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

        frames.append(Frame(frame_datetime, rate, mcs_index, probe_ssid))

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
