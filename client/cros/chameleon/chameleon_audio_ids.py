# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Audio port ids shared in Chameleon audio test framework"""


class ChameleonIds(object):
    """Ids for audio ports on Chameleon

    An Id is composed by host name 'Chameleon' and interface name e.g. 'HDMI'.
    Note that the interface name must match what get_connector_type method
    returns on a ChameleonPort so ChameleonPortFinder can find the port.

    """
    HDMI = 'Chameleon HDMI'
    LINEIN = 'Chameleon LineIn'
    LINEOUT = 'Chameleon LineOut'
    MIC = 'Chameleon Mic'

    SINK_PORTS = [HDMI, LINEIN, MIC]
    SOURCE_PORTS = [LINEOUT]


class CrosIds(object):
    """Ids for audio ports on Cros device.

    Note that an bidirectional interface like 3.5mm jack is separated to
    two interfaces, that is, 'Headphone' and 'External Mic'.

    """
    HDMI = 'Cros HDMI'
    HEADPHONE = 'Cros Headphone'
    EXTERNAL_MIC = 'Cros External Mic'
    SPEAKER = 'Cros Speaker'
    INTERNAL_MIC = 'Cros Internal Mic'

    SINK_PORTS = [EXTERNAL_MIC, INTERNAL_MIC]
    SOURCE_PORTS = [HDMI, HEADPHONE, SPEAKER]


class PeripheralIds(object):
    """Ids for peripherals.

    These peripherals will be accessible by Cros device/Chameleon through
    audio board.

    """
    SPEAKER = 'Peripheral Speaker'
    MIC = 'Peripheral Mic'

    # Peripheral devices should have two roles but we only care one.
    # For example, to test internal microphone on Cros device:
    #
    #                                         (air)
    #                    Peripheral Speaker -------> Internal Microphone
    #                         ------                  ------
    # Chameleon LineOut ----> |    |                  |    |
    #                         ------                  ------
    #                        Audio board             Cros device
    #
    # In the above example, peripheral speaker is a sink as it takes signal
    # from audio board. It should be a source as peripheral speaker transfer
    # signal to internal microphone of Cros device,
    # However, we do not abstract air as a link because it does not contain
    # properties like level, channel_map, occupied to manipulate.
    # So, we set peripheral speaker to be a sink to reflect the part related
    # to audio bus.
    #
    # For example, to test internal speaker on Cros device:
    #
    #                                         (air)
    #                    Peripheral Micropone <----- Internal Speaker
    #                         ------                  ------
    # Chameleon LineIn <----  |    |                  |    |
    #                         ------                  ------
    #                        Audio board             Cros device
    #
    # In the above example, peripheral microphone is a source as it feeds signal
    # to audio board. It should be a sink as peripheral microphone receives
    # signal from internal speaker of Cros device.
    # However, we do not abstract air as a link because it does not contain
    # properties like level, channel_map, occupied to manipulate.
    # So, we set peripheral microphone to be a source to reflect the part related
    # to audio bus.
    SOURCE_PORTS = [MIC]
    SINK_PORTS = [SPEAKER]


SINK_PORTS = []
for cls in [ChameleonIds, CrosIds, PeripheralIds]:
    SINK_PORTS += cls.SINK_PORTS

SOURCE_PORTS = []
for cls in [ChameleonIds, CrosIds, PeripheralIds]:
    SOURCE_PORTS += cls.SOURCE_PORTS


def get_host(port_id):
    """Parses given port_id to get host name.

    @param port_id: A string, that is, id in ChameleonIds, CrosIds, or
                    PeripheralIds.

    @returns: Host name. A string in ['Chameleon', 'Cros', 'Peripheral'].

    @raises: ValueError if port_id is invalid.

    """
    host = port_id.split()[0]
    if host not in ['Chameleon', 'Cros', 'Peripheral']:
        raise ValueError('Not a valid port id: %r' % port_id)
    return host


def get_interface(port_id):
    """Parses given port_id to get interface name.

    @param port_id: A string, that is, id in ChameleonIds, CrosIds, or
                    PeripheralIds.

    @returns: Interface name. A string, e.g. 'HDMI', 'LineIn'.

    @raises: ValueError if port_id is invalid.

    """
    try:
        return port_id.split(' ', 1)[1]
    except IndexError:
        raise ValueError('Not a valid port id: %r' % port_id)


def get_role(port_id):
    """Gets the role of given port_id.

    @param port_id: A string, that is, id in ChameleonIds, CrosIds, or
                    PeripheralIds.

    @returns: 'source' or 'sink'.

    @raises: ValueError if port_id is invalid.

    """
    if port_id in SOURCE_PORTS:
        return 'source'
    if port_id in SINK_PORTS:
        return 'sink'
    raise ValueError('Not a valid port id: %r' % port_id)
