# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides the audio board interface."""


from autotest_lib.client.cros.chameleon import chameleon_audio_ids as ids


class AudioBoard(object):
    """AudioBoard is an abstraction of an audio board on a Chameleon board.

    It provides methods to control audio board.

    A ChameleonConnection object is passed to the construction.

    """
    def __init__(self, chameleon_connection):
        """Constructs an AudioBoard.

        @param chameleon_connection: A ChameleonConnection object.

        """
        self._audio_buses = {
                1: AudioBus(1, chameleon_connection),
                2: AudioBus(2, chameleon_connection)}


    def get_audio_bus(self, bus_index):
        """Gets an audio bus on this audio board.

        @param bus_index: The bus index 1 or 2.

        @returns: An AudioBus object.

        """
        return self._audio_buses[bus_index]


class AudioBus(object):
    """AudioBus is an abstraction of an audio bus on an audio board.

    It provides methods to control audio bus.

    A ChameleonConnection object is passed to the construction.

    @properties:
        bus_index: The bus index 1 or 2.

    """
    # Maps port id defined in chameleon_audio_ids to endpoint name used in
    # chameleond audio bus API.
    _PORT_ID_AUDIO_BUS_ENDPOINT_MAP = {
            ids.ChameleonIds.LINEIN: 'Chameleon FPGA line-in',
            ids.ChameleonIds.LINEOUT: 'Chameleon FPGA line-out',
            ids.CrosIds.HEADPHONE: 'Cros device headphone',
            ids.CrosIds.EXTERNAL_MIC: 'Cros device external microphone',
            ids.PeripheralIds.SPEAKER: 'Peripheral speaker',
            ids.PeripheralIds.MIC: 'Peripheral microphone'}

    def __init__(self, bus_index, chameleon_connection):
        """Constructs an AudioBus.

        @param bus_index: The bus index 1 or 2.
        @param chameleon_connection: A ChameleonConnection object.

        """
        self.bus_index = bus_index
        self._chameleond_proxy = chameleon_connection.chameleond_proxy


    def _get_endpoint_name(self, port_id):
        """Gets the endpoint name used in audio bus API.

        @param port_id: A string, that is, id in ChameleonIds, CrosIds, or
                        PeripheralIds defined in chameleon_audio_ids.

        @returns: The endpoint name for the port used in audio bus API.

        """
        return self._PORT_ID_AUDIO_BUS_ENDPOINT_MAP[port_id]


    def connect(self, port_id):
        """Connects an audio port to this audio bus.

        @param port_id: A string, that is, id in ChameleonIds, CrosIds, or
                        PeripheralIds defined in chameleon_audio_ids.

        """
        endpoint = self._get_endpoint_name(port_id)
        self._chameleond_proxy.AudioBoardConnect(self.bus_index, endpoint)


    def disconnect(self, port_id):
        """Disconnects an audio port from this audio bus.

        @param port_id: A string, that is, id in ChameleonIds, CrosIds, or
                        PeripheralIds defined in chameleon_audio_ids.

        """
        endpoint = self._get_endpoint_name(port_id)
        self._chameleond_proxy.AudioBoardDisconnect(self.bus_index, endpoint)
