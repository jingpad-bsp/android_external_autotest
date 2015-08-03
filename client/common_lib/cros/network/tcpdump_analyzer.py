# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error

PYSHARK_LOAD_TIMEOUT = 2
FRAME_FIELD_RADIOTAP_DATARATE = 'radiotap.datarate'
FRAME_FIELD_RADIOTAP_MCS_INDEX = 'radiotap.mcs_index'
FRAME_FIELD_WLAN_FRAME_TYPE = 'wlan.fc_type_subtype'
FRAME_FIELD_WLAN_MGMT_SSID = 'wlan_mgt.ssid'
RADIOTAP_KNOWN_BAD_FCS_REJECTOR = (
    'not radiotap.flags.badfcs or radiotap.flags.badfcs==0')
WLAN_PROBE_REQ_FRAME_TYPE = '0x04'
WLAN_PROBE_REQ_ACCEPTOR = 'wlan.fc.type_subtype==0x04'
PYSHARK_BROADCAST_SSID = 'SSID: '
BROADCAST_SSID = ''


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


def _fetch_frame_field_value(frame, field):
    """
    Retrieve the value of |field| within the |frame|.

    @param frame: Pyshark packet object corresponding to a captured frame.
    @param field: Field for which the value needs to be extracted from |frame|.

    @return Value extracted from the frame if the field exists, else None.

    """
    layer_object = frame
    for layer in field.split('.'):
        try:
            layer_object = getattr(layer_object, layer)
        except AttributeError:
            return None
    return layer_object


def _match_frame_field_with_value(frame, field, match_value):
    """
    Check if the value of |field| within the |frame| matches |match_value|.

    @param frame: Pyshark packet object corresponding to a captured frame.
    @param field: Field for which the value needs to be extracted from |frame|.
    @param match_value: Value to be matched.

    @return True if |match_value| macthes the value retrieved from the frame,
            False otherwise.

    """
    value = _fetch_frame_field_value(frame, field)
    return (match_value == value)


def _open_capture(pcap_path, display_filter):
    """
    Get pyshark packet object parsed contents of a pcap file.

    @param pcap_path: string path to pcap file.
    @param display_filter: string filter to apply to captured frames.

    @return list of Pyshark packet objects.

    """
    import pyshark
    capture = pyshark.FileCapture(input_file=pcap_path,
                                  display_filter=display_filter)
    capture.load_packets(timeout=PYSHARK_LOAD_TIMEOUT)
    return capture


def get_frames(local_pcap_path, display_filter, bad_fcs):
    """
    Get a parsed representation of the contents of a pcap file.

    @param local_pcap_path: string path to a local pcap file on the host.
    @param diplay_filter: string filter to apply to captured frames.
    @param bad_fcs: string 'include' or 'discard'

    @return list of Frame structs.

    """
    if bad_fcs == 'include':
        display_filter = display_filter
    elif bad_fcs == 'discard':
        display_filter = '(%s) and (%s)' % (RADIOTAP_KNOWN_BAD_FCS_REJECTOR,
                                            display_filter)
    else:
        raise error.TestError('Invalid value for bad_fcs arg: %s.' % bad_fcs)

    logging.debug('Capture: %s, Filter: %s', local_pcap_path, display_filter)
    capture_frames = _open_capture(local_pcap_path, display_filter)
    frames = []
    logging.info('Parsing frames')

    for frame in capture_frames:
        rate = _fetch_frame_field_value(frame, FRAME_FIELD_RADIOTAP_DATARATE)
        if rate:
            rate = float(rate)
        else:
            logging.debug('Found bad capture frame: %s', frame)
            continue

        frametime = frame.sniff_time

        mcs_index = _fetch_frame_field_value(frame, FRAME_FIELD_RADIOTAP_MCS_INDEX)
        if mcs_index:
            mcs_index = int(mcs_index)

        # Get the SSID for any probe requests
        is_probe_req = _match_frame_field_with_value(
                frame, FRAME_FIELD_WLAN_FRAME_TYPE, WLAN_PROBE_REQ_FRAME_TYPE)
        if is_probe_req:
            probe_ssid = _fetch_frame_field_value(
                    frame, FRAME_FIELD_WLAN_MGMT_SSID)
            # Since the SSID name is a variable length field, there seems to be
            # a bug in the pyshark parsing, it returns 'SSID: ' instead of ''
            # for broadcast SSID's.
            if probe_ssid == PYSHARK_BROADCAST_SSID:
                probe_ssid = BROADCAST_SSID
        else:
            probe_ssid = None

        frames.append(Frame(frametime, rate, mcs_index, probe_ssid))

    return frames


def get_probe_ssids(local_pcap_path, probe_sender=None):
    """
    Get the SSIDs that were named in 802.11 probe requests frames.

    Parse a pcap, returning all the SSIDs named in 802.11 probe
    request frames. If |probe_sender| is specified, only probes
    from that MAC address will be considered.

    @param pcap_path: string path to a local pcap file on the host.
    @param remote_host: Host object (if the file is remote).
    @param probe_sender: MAC address of the device sending probes.

    @return: A frozenset of the SSIDs that were probed.

    """
    if probe_sender:
        diplay_filter = '%s and wlan.addr==%s' % (
                WLAN_PROBE_REQ_ACCEPTOR, probe_sender)
    else:
        diplay_filter = WLAN_PROBE_REQ_ACCEPTOR

    frames = get_frames(local_pcap_path, diplay_filter, bad_fcs='discard')

    return frozenset(
            [frame.probe_ssid for frame in frames
             if frame.probe_ssid is not None])
