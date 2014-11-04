# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import httplib
import socket
import time
import xmlrpclib

from PIL import Image

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.chameleon import edid


CHAMELEON_PORT = 9992


class ChameleonConnectionError(error.TestError):
    """Indicates that connecting to Chameleon failed.

    It is fatal to the test unless caught.
    """
    pass


class ChameleonConnection(object):
    """ChameleonConnection abstracts the network connection to the board.

    ChameleonBoard and ChameleonPort use it for accessing Chameleon RPC.

    """

    def __init__(self, hostname, port=CHAMELEON_PORT):
        """Constructs a ChameleonConnection.

        @param hostname: Hostname the chameleond process is running.
        @param port: Port number the chameleond process is listening on.

        @raise ChameleonConnectionError if connection failed.
        """
        self.chameleond_proxy = ChameleonConnection._create_server_proxy(
                hostname, port)


    @staticmethod
    def _create_server_proxy(hostname, port):
        """Creates the chameleond server proxy.

        @param hostname: Hostname the chameleond process is running.
        @param port: Port number the chameleond process is listening on.

        @return ServerProxy object to chameleond.

        @raise ChameleonConnectionError if connection failed.
        """
        remote = 'http://%s:%s' % (hostname, port)
        chameleond_proxy = xmlrpclib.ServerProxy(remote, allow_none=True)
        # Call a RPC to test.
        try:
            chameleond_proxy.ProbeInputs()
        except (socket.error,
                xmlrpclib.ProtocolError,
                httplib.BadStatusLine) as e:
            raise ChameleonConnectionError(e)
        return chameleond_proxy


class ChameleonBoard(object):
    """ChameleonBoard is an abstraction of a Chameleon board.

    A Chameleond RPC proxy is passed to the construction such that it can
    use this proxy to control the Chameleon board.

    """

    def __init__(self, chameleon_connection):
        """Construct a ChameleonBoard.

        @param chameleon_connection: ChameleonConnection object.
        """
        self._chameleond_proxy = chameleon_connection.chameleond_proxy


    def reset(self):
        """Resets Chameleon board."""
        self._chameleond_proxy.Reset()


    def is_healthy(self):
        """Returns if the Chameleon is healthy or any repair is needed.

        @return: True if the Chameleon is healthy;
                 otherwise, False, need to repair.
        """
        return self._chameleond_proxy.IsHealthy()


    def repair(self):
        """Repairs the Chameleon.

        It is a synchronous call. It returns after repairs.
        """
        repair_time = self._chameleond_proxy.Repair()
        time.sleep(repair_time)


    def get_all_ports(self):
        """Gets all the ports on Chameleon board which are connected.

        @return: A list of ChameleonPort objects.
        """
        ports = self._chameleond_proxy.ProbePorts()
        return [ChameleonPort(self._chameleond_proxy, port) for port in ports]


    def get_all_inputs(self):
        """Gets all the input ports on Chameleon board which are connected.

        @return: A list of ChameleonPort objects.
        """
        ports = self._chameleond_proxy.ProbeInputs()
        return [ChameleonPort(self._chameleond_proxy, port) for port in ports]


    def get_all_outputs(self):
        """Gets all the output ports on Chameleon board which are connected.

        @return: A list of ChameleonPort objects.
        """
        ports = self._chameleond_proxy.ProbeOutputs()
        return [ChameleonPort(self._chameleond_proxy, port) for port in ports]


    def get_label(self):
        """Gets the label which indicates the display connection.

        @return: A string of the label, like 'hdmi', 'dp_hdmi', etc.
        """
        connectors = []
        for port in self._chameleond_proxy.ProbeInputs():
            if self._chameleond_proxy.HasVideoSupport(port):
                connector = self._chameleond_proxy.GetConnectorType(port).lower()
                connectors.append(connector)
        # Eliminate duplicated ports. It simplifies the labels of dual-port
        # devices, i.e. dp_dp categorized into dp.
        return '_'.join(sorted(set(connectors)))


class ChameleonPort(object):
    """ChameleonPort is an abstraction of a general port of a Chameleon board.

    It only contains some common methods shared with audio and video ports.

    A Chameleond RPC proxy and an port_id are passed to the construction.
    The port_id is the unique identity to the port.
    """

    def __init__(self, chameleond_proxy, port_id):
        """Construct a ChameleonPort.

        @param chameleond_proxy: Chameleond RPC proxy object.
        @param port_id: The ID of the input port.
        """
        self.chameleond_proxy = chameleond_proxy
        self.port_id = port_id


    def get_connector_id(self):
        """Returns the connector ID.

        @return: A number of connector ID.
        """
        return self.port_id


    def get_connector_type(self):
        """Returns the human readable string for the connector type.

        @return: A string, like "VGA", "DVI", "HDMI", or "DP".
        """
        return self.chameleond_proxy.GetConnectorType(self.port_id)


    def has_audio_support(self):
        """Returns if the input has audio support.

        @return: True if the input has audio support; otherwise, False.
        """
        return self.chameleond_proxy.HasAudioSupport(self.port_id)


    def has_video_support(self):
        """Returns if the input has video support.

        @return: True if the input has video support; otherwise, False.
        """
        return self.chameleond_proxy.HasVideoSupport(self.port_id)


    def plug(self):
        """Asserts HPD line to high, emulating plug."""
        self.chameleond_proxy.Plug(self.port_id)


    def unplug(self):
        """Deasserts HPD line to low, emulating unplug."""
        self.chameleond_proxy.Unplug(self.port_id)


    @property
    def plugged(self):
        """
        @returns True if this port is plugged to Chameleon, False otherwise.

        """
        return self.chameleond_proxy.IsPlugged(self.port_id)


class ChameleonVideoInput(ChameleonPort):
    """ChameleonVideoInput is an abstraction of a video input port.

    It contains some special methods to control a video input.
    """

    def __init__(self, chameleon_port):
        """Construct a ChameleonVideoInput.

        @param chameleon_port: A general ChameleonPort object.
        """
        self.chameleond_proxy = chameleon_port.chameleond_proxy
        self.port_id = chameleon_port.port_id


    def wait_video_input_stable(self, timeout=None):
        """Waits the video input stable or timeout.

        @param timeout: The time period to wait for.

        @return: True if the video input becomes stable within the timeout
                 period; otherwise, False.
        """
        return self.chameleond_proxy.WaitVideoInputStable(self.port_id,
                                                          timeout)


    def read_edid(self):
        """Reads the EDID.

        @return: An Edid object.
        """
        # Read EDID without verify. It may be made corrupted as intended
        # for the test purpose.
        return edid.Edid(self.chameleond_proxy.ReadEdid(self.port_id).data,
                         skip_verify=True)


    def apply_edid(self, edid):
        """Applies the given EDID.

        @param edid: An Edid object.
        """
        edid_id = self.chameleond_proxy.CreateEdid(xmlrpclib.Binary(edid.data))
        self.chameleond_proxy.ApplyEdid(self.port_id, edid_id)
        self.chameleond_proxy.DestroyEdid(edid_id)


    def fire_hpd_pulse(self, deassert_interval_usec, assert_interval_usec=None,
                       repeat_count=1, end_level=1):

        """Fires one or more HPD pulse (low -> high -> low -> ...).

        @param deassert_interval_usec: The time in microsecond of the
                deassert pulse.
        @param assert_interval_usec: The time in microsecond of the
                assert pulse. If None, then use the same value as
                deassert_interval_usec.
        @param repeat_count: The count of HPD pulses to fire.
        @param end_level: HPD ends with 0 for LOW (unplugged) or 1 for
                HIGH (plugged).
        """
        self.chameleond_proxy.FireHpdPulse(
                self.port_id, deassert_interval_usec,
                assert_interval_usec, repeat_count, int(bool(end_level)))


    def fire_mixed_hpd_pulses(self, widths):
        """Fires one or more HPD pulses, starting at low, of mixed widths.

        One must specify a list of segment widths in the widths argument where
        widths[0] is the width of the first low segment, widths[1] is that of
        the first high segment, widths[2] is that of the second low segment...
        etc. The HPD line stops at low if even number of segment widths are
        specified; otherwise, it stops at high.

        @param widths: list of pulse segment widths in usec.
        """
        self.chameleond_proxy.FireMixedHpdPulses(self.port_id, widths)


    def capture_screen(self):
        """Captures Chameleon framebuffer.

        @return An Image object.
        """
        return Image.fromstring(
                'RGB',
                self.get_resolution(),
                self.chameleond_proxy.DumpPixels(self.port_id).data)


    def get_resolution(self):
        """Gets the source resolution.

        @return: A (width, height) tuple.
        """
        # The return value of RPC is converted to a list. Convert it back to
        # a tuple.
        return tuple(self.chameleond_proxy.DetectResolution(self.port_id))


class ChameleonAudioInput(ChameleonPort):
    """ChameleonAudioInput is an abstraction of an audio input port.

    It contains some special methods to control an audio input.
    """

    def __init__(self, chameleon_port):
        """Construct a ChameleonAudioInput.

        @param chameleon_port: A general ChameleonPort object.
        """
        self.chameleond_proxy = chameleon_port.chameleond_proxy
        self.port_id = chameleon_port.port_id


    def start_capturing_audio(self):
        """Starts capturing audio."""
        return self.chameleond_proxy.StartCapturingAudio(self.port_id)


    def stop_capturing_audio(self):
        """Stops capturing audio.

        Returns:
          A tuple (data, format).
          data: The captured binary data.
          format: A dict containing:
            file_type: 'raw' or 'wav'.
            sample_format: 'S32_LE' for 32-bit signed integer in little-endian.
              Refer to aplay manpage for other formats.
            channel: channel number.
            rate: sampling rate.
        """
        rpc_data, data_format = self.chameleond_proxy.StopCapturingAudio(
                self.port_id)
        return rpc_data.data, data_format


def make_chameleon_hostname(dut_hostname):
    """Given a DUT's hostname, returns the hostname of its Chameleon.

    @param dut_hostname: Hostname of a DUT.

    @return Hostname of the DUT's Chameleon.
    """
    host_parts = dut_hostname.split('.')
    host_parts[0] = host_parts[0] + '-chameleon'
    return '.'.join(host_parts)


def create_chameleon_board(dut_hostname, args):
    """Given either DUT's hostname or argments, creates a ChameleonBoard object.

    If the DUT's hostname is in the lab zone, it connects to the Chameleon by
    append the hostname with '-chameleon' suffix. If not, checks if the args
    contains the key-value pair 'chameleon_host=IP'.

    @param dut_hostname: Hostname of a DUT.
    @param args: A string of arguments passed from the command line.

    @return A ChameleonBoard object.

    @raise ChameleonConnectionError if unknown hostname.
    """
    connection = None
    hostname = make_chameleon_hostname(dut_hostname)
    if utils.host_is_in_lab_zone(hostname):
        connection = ChameleonConnection(hostname)
    else:
        args_dict = utils.args_to_dict(args)
        hostname = args_dict.get('chameleon_host', None)
        port = args_dict.get('chameleon_port', CHAMELEON_PORT)
        if hostname:
            connection = ChameleonConnection(hostname, port)
        else:
            raise ChameleonConnectionError('No chameleon_host is given in args')

    return ChameleonBoard(connection)
