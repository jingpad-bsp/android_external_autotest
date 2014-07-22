# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
import xmlrpclib

from PIL import Image

from autotest_lib.server.cros.chameleon import edid


class ChameleonBoard(object):
    """ChameleonBoard is an abstraction of a Chameleon board.

    A Chameleond RPC proxy is passed to the construction such that it can
    use this proxy to control the Chameleon board.
    """

    def __init__(self, chameleond_proxy):
        """Construct a ChameleonBoard.

        @param chameleond_proxy: Chameleond RPC proxy object.
        """
        self._chameleond_proxy = chameleond_proxy


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
        ports = self._chameleond_proxy.ProbeInputs()
        return [ChameleonPort(self._chameleond_proxy, port) for port in ports]


    def get_pixel_format(self):
        """Gets the pixel format for the output of DumpPixels.

        @return: A string of the format, like 'rgba', 'bgra', 'rgb', etc.
        """
        return self._chameleond_proxy.GetPixelFormat()


    def get_pixel_length(self):
        """Gets the length of a pixel, which is returned from DumpPixels().

        @return: A number of length, in byte.
        """
        return len(self.get_pixel_format())


class ChameleonPort(object):
    """ChameleonPort is an abstraction of a port of a Chameleon board.

    A Chameleond RPC proxy and an input_id are passed to the construction.
    The input_id is the unique identity to the port.
    """

    def __init__(self, chameleond_proxy, input_id):
        """Construct a ChameleonPort.

        @param chameleond_proxy: Chameleond RPC proxy object.
        @param input_id: The ID of the input port.
        """
        self._chameleond_proxy = chameleond_proxy
        self._input_id = input_id


    def get_connector_id(self):
        """Returns the connector ID.

        @return: A number of connector ID.
        """
        return self._input_id


    def get_connector_type(self):
        """Returns the human readable string for the connector type.

        @return: A string, like "VGA", "DVI", "HDMI", or "DP".
        """
        return self._chameleond_proxy.GetConnectorType(self._input_id)


    def wait_video_input_stable(self, timeout=None):
        """Waits the video input stable or timeout.

        @param timeout: The time period to wait for.

        @return: True if the video input becomes stable within the timeout
                 period; otherwise, False.
        """
        return self._chameleond_proxy.WaitVideoInputStable(self._input_id,
                                                           timeout)


    def read_edid(self):
        """Reads the EDID.

        @return: An Edid object.
        """
        # Read EDID without verify. It may be made corrupted as intended
        # for the test purpose.
        return edid.Edid(self._chameleond_proxy.ReadEdid(self._input_id).data,
                         skip_verify=True)


    def apply_edid(self, edid):
        """Applies the given EDID.

        @param edid: An Edid object.
        """
        edid_id = self._chameleond_proxy.CreateEdid(xmlrpclib.Binary(edid.data))
        self._chameleond_proxy.ApplyEdid(self._input_id, edid_id)
        self._chameleond_proxy.DestroyEdid(edid_id)


    def plug(self):
        """Asserts HPD line to high, emulating plug."""
        self._chameleond_proxy.Plug(self._input_id)


    def unplug(self):
        """Deasserts HPD line to low, emulating unplug."""
        self._chameleond_proxy.Unplug(self._input_id)


    def fire_hpd_pulse(self, deassert_interval_usec, assert_interval_usec=None,
                       repeat_count=1):
        """Fires a HPD pulse (high -> low -> high) or multiple HPD pulses.

        @param deassert_interval_usec: The time of the deassert pulse.
        @param assert_interval_usec: The time of the assert pulse.
        @param repeat_count: The count of repeating the HPD pulses.
        """
        self._chameleond_proxy.FireHpdPulse(
                self._input_id, deassert_interval_usec, assert_interval_usec,
                repeat_count)


    def capture_screen(self):
        """Captures Chameleon framebuffer.

        @return An Image object.
        """
        image = Image.fromstring(
                self._chameleond_proxy.GetPixelFormat().upper(),
                self.get_resolution(),
                self._chameleond_proxy.DumpPixels(self._input_id).data)
        return image.convert('RGB')


    def get_resolution(self):
        """Gets the source resolution.

        @return: A (width, height) tuple.
        """
        # The return value of RPC is converted to a list. Convert it back to
        # a tuple.
        return tuple(self._chameleond_proxy.DetectResolution(self._input_id))
