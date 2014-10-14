# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import utils
from collections import namedtuple


ChameleonPorts = namedtuple('ChameleonPorts', 'connected failed')


class ChameleonPortFinder(object):
    """
    Responsible for finding all ports connected to the chameleon board.

    """

    def __init__(self, chameleon_board):
        """
        @param chameleon_board: a ChameleonBoard object representing the Chameleon
                                board whose ports we are interested in finding.

        """
        self.chameleon_board = chameleon_board
        self._TIMEOUT_VIDEO_STABLE_PROBE = 10
        self.connected = None
        self.failed = None


    def find_all_video_ports(self):
        """
        @returns a named tuple ChameleonPorts() containing a list of connected
                 video ports as the first element and failed ports as second
                 element.

        """

        connected_ports = []
        dut_failed_ports = []

        for chameleon_port in self.chameleon_board.get_all_ports():
            # Skip the non-video port.
            if not chameleon_port.has_video_support():
                continue

            connector_type = chameleon_port.get_connector_type()
            # Try to plug the port such that DUT can detect it.
            was_plugged = chameleon_port.plugged

            if not was_plugged:
                chameleon_port.plug()
            # DUT takes some time to respond. Wait until the video signal
            # to stabilize.
            chameleon_port.wait_video_input_stable(
                self._TIMEOUT_VIDEO_STABLE_PROBE)

            # Add the connected ports if they are detected by xrandr.
            xrandr_output = utils.get_xrandr_output_state()
            for output in xrandr_output.iterkeys():
                if output.startswith(connector_type):
                    connected_ports.append(chameleon_port)
                    break
            else:
                dut_failed_ports.append(chameleon_port)

            # Unplug the port afterward if it wasn't plugged to begin with.
            if not was_plugged:
                chameleon_port.unplug()

        self.connected = connected_ports
        self.failed = dut_failed_ports

        return ChameleonPorts(connected_ports, dut_failed_ports)


    def find_video_port(self, interface):
        """
        @param interface: string, the interface. e.g: HDMI, DP, VGA
        @returns a ChameleonPort object if port is found, else None.

        """
        connected_ports = self.find_all_video_ports().connected

        for port in connected_ports:
            if port.get_connector_type().lower() == interface.lower():
                return port

        return None


    def __str__(self):
        ports_to_str = lambda ports: ', '.join(
                '%s(%d)' % (p.get_connector_type(), p.get_connector_id())
                for p in ports)

        text = 'No port information. Did you run find_all_video_ports() ?'

        if self.connected:
            text = ('Detected %d connected port(s): %s.\t'
                    % (len(self.connected), ports_to_str(self.connected)))

        if self.failed:
            text += ('DUT failed to detect Chameleon ports: %s'
                     % ports_to_str(self.failed))

        return text
