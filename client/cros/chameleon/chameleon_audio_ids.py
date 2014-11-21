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

    INPUT_PORTS = [HDMI, LINEIN]
    OUTPUT_PORTS = [LINEOUT]


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

    INPUT_PORTS = [EXTERNAL_MIC, INTERNAL_MIC]
    OUTPUT_PORTS = [HDMI, HEADPHONE, SPEAKER]


class PeripheralIds(object):
    """Ids for peripherals.

    These peripherals will be accessible by Cros device/Chameleon through
    audio board.

    """
    SPEAKER = 'Peripheral Speaker'
    MIC = 'Peripheral Mic'

    INPUT_PORTS = [MIC]
    OUTPUT_PORTS = [SPEAKER]


INPUT_PORTS = []
for cls in [ChameleonIds, CrosIds, PeripheralIds]:
    INPUT_PORTS += cls.INPUT_PORTS

OUTPUT_PORTS = []
for cls in [ChameleonIds, CrosIds, PeripheralIds]:
    OUTPUT_PORTS += cls.OUTPUT_PORTS


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


def get_direction(port_id):
    """Gets the direction of given port_id.

    @param port_id: A string, that is, id in ChameleonIds, CrosIds, or
                    PeripheralIds.

    @returns: 'Input' or 'Output'.

    @raises: ValueError if port_id is invalid.

    """
    if port_id in INPUT_PORTS:
        return 'Input'
    if port_id in OUTPUT_PORTS:
        return 'Output'
    raise ValueError('Not a valid port id: %r' % port_id)
