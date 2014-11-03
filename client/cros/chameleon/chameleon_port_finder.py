# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple

ChameleonPorts = namedtuple('ChameleonPorts', 'connected failed')


class ChameleonPortFinder(object):
    """
    Responsible for finding all ports connected to the chameleon board.

    It does not verify if these ports are connected to DUT.

    """

    def __init__(self, chameleon_board):
        """
        @param chameleon_board: a ChameleonBoard object representing the
                                Chameleon board whose ports we are interested
                                in finding.

        """
        self.chameleon_board = chameleon_board
        self.connected = None
        self.failed = None


    def find_all_ports(self):
        """
        @returns a named tuple ChameleonPorts() containing a list of connected
                 ports as the first element and failed ports as second element.

        """
        connected_ports = self.chameleon_board.get_all_ports()
        dut_failed_ports = []

        return ChameleonPorts(connected_ports, dut_failed_ports)


    def find_port(self, interface):
        """
        @param interface: string, the interface. e.g: HDMI, DP, VGA
        @returns a ChameleonPort object if port is found, else None.

        """
        connected_ports = self.find_all_ports().connected

        for port in connected_ports:
            if port.get_connector_type().lower() == interface.lower():
                return port

        return None


    def __str__(self):
        ports_to_str = lambda ports: ', '.join(
                '%s(%d)' % (p.get_connector_type(), p.get_connector_id())
                for p in ports)

        if self.connected is None:
            text = 'No port information. Did you run find_all_ports()?'
        elif self.connected == []:
            text = 'No port detected on the Chameleon board.'
        else:
            text = ('Detected %d connected port(s): %s.\t'
                    % (len(self.connected), ports_to_str(self.connected)))

        if self.failed:
            text += ('DUT failed to detect Chameleon ports: %s'
                     % ports_to_str(self.failed))

        return text


class ChameleonVideoPortFinder(ChameleonPortFinder):
    """
    Responsible for finding all video ports connected to the chameleon board.

    It also verifies if these ports are connected to DUT.

    """

    def __init__(self, chameleon_board, display_facade):
        """
        @param chameleon_board: a ChameleonBoard object representing the
                                Chameleon board whose ports we are interested
                                in finding.
        @param display_facade: a display facade object, to access the DUT
                               display functionality, either locally or
                               remotely.

        """
        super(ChameleonVideoPortFinder, self).__init__(chameleon_board)
        self.display_facade = display_facade
        self._TIMEOUT_VIDEO_STABLE_PROBE = 10


    def find_all_ports(self):
        """
        @returns a named tuple ChameleonPorts() containing a list of connected
                 video ports as the first element and failed ports as second
                 element.

        """
        connected_ports = []
        dut_failed_ports = []

        all_ports = super(ChameleonVideoPortFinder, self).find_all_ports()
        for port in all_ports.connected:
            # Skip the non-video port.
            if not port.has_video_support():
                continue

            connector_type = port.get_connector_type()
            # Try to plug the port such that DUT can detect it.
            was_plugged = port.plugged

            if not was_plugged:
                port.plug()
            # DUT takes some time to respond. Wait until the video signal
            # to stabilize.
            port.wait_video_input_stable(self._TIMEOUT_VIDEO_STABLE_PROBE)

            output = self.display_facade.get_external_connector_name()
            if output and output.startswith(connector_type):
                connected_ports.append(port)
            else:
                dut_failed_ports.append(port)

            # Unplug the port afterward if it wasn't plugged to begin with.
            if not was_plugged:
                port.unplug()

        self.connected = connected_ports
        self.failed = dut_failed_ports

        return ChameleonPorts(connected_ports, dut_failed_ports)


class ChameleonAudioPortFinder(ChameleonPortFinder):
    """
    Responsible for finding all audio ports connected to the chameleon board.

    It does not verify if these ports are connected to DUT.

    """

    def find_all_ports(self):
        """
        @returns a named tuple ChameleonPorts() containing a list of connected
                 audio ports as the first element and failed ports as second
                 element.

        """
        all_ports = super(ChameleonAudioPortFinder, self).find_all_ports()
        connected_ports = [port for port in all_ports.connected
                           if port.has_audio_support()]
        dut_failed_ports = []

        return ChameleonPorts(connected_ports, dut_failed_ports)
