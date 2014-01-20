# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side resolution display test using the Chameleon board."""

import logging
import math
import os
import re
import struct
import xmlrpclib

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import enum, error
from autotest_lib.client.cros import constants, httpd
from autotest_lib.server import autotest, test

CONNECTOR = enum.Enum('HDMI', 'DP', 'DVI', string_values=True)

# pylint: disable=E1101

class display_Resolution(test.test):
    """Server side external display test.

    This test talks to a Chameleon board and a DUT to set up, run, and verify
    external display function of the DUT.
    """
    version = 1
    XMLRPC_CONNECT_TIMEOUT = 30
    HTTPD_PORT = 12345
    X_ENV_VARIABLES = 'DISPLAY=:0.0 XAUTHORITY=/home/chronos/.Xauthority'
    RESOLUTION_TEST_LIST = {
            CONNECTOR.DP: [
                    (1280, 800),
                    (1440, 900),
                    (1600, 900),
                    (1680, 1050),
                    (1920, 1080)
            ],
            CONNECTOR.HDMI: [
                    (1280, 720),
                    (1920, 1080)
            ]}

    def initialize(self, host):
        self._active_output = None
        self._connector_id = None
        self._connector_name = None
        self._errors = []
        self._test_data_dir = os.path.join(
                self.bindir, 'display_Resolution_test_data')
        self._display_xmlrpc_client = None
        self._host = None
        self._my_ip = None
        self._http_listener = httpd.HTTPListener(
                port=self.HTTPD_PORT,
                docroot=os.path.join(self._test_data_dir, 'calibration_images'))
        self._http_listener.run()
        self._chameleon_board = host.chameleon

    def cleanup(self):
        super(display_Resolution, self).cleanup()
        self._http_listener.stop()

    def run_once(self, host, usb_serial=None, test_mirrored=False,
                 test_suspend_resume=False):
        self._host = host
        client_at = autotest.Autotest(self._host)
        client_at.install()

        self._display_xmlrpc_client = host.xmlrpc_connect(
                constants.DISPLAY_TESTING_XMLRPC_SERVER_COMMAND,
                constants.DISPLAY_TESTING_XMLRPC_SERVER_PORT,
                command_name=(
                    constants.DISPLAY_TESTING_XMLRPC_SERVER_CLEANUP_PATTERN
                ),
                ready_test_name=(
                    constants.DISPLAY_TESTING_XMLRPC_SERVER_READY_METHOD),
                timeout_seconds=self.XMLRPC_CONNECT_TIMEOUT)
        # SSH_CONNECTION is of the form: [client_ip] [client_port] [server_ip]
        # [server_port].
        self._my_ip = re.search(
                r'([0-9.]+) \d+ [0-9.]+ \d+',
                host.run('echo $SSH_CONNECTION').stdout).group(1)

        output, connector_id, connector_name = self.get_ext_output_name()
        if output is None:
            raise error.TestError('DUT and Chameleon board not connected')
        self._active_output = output
        self._connector_id = connector_id
        self._connector_name = connector_name

        for resolution in self.RESOLUTION_TEST_LIST[connector_name]:
            try:
                self.set_up_chameleon(resolution)
                logging.info('Reconnect output: %s', output)
                self._display_xmlrpc_client.reconnect_output(output)
                logging.info('Wait output to connect: %s', output)
                self._display_xmlrpc_client.wait_output_connected(output)
                utils.wait_for_value(lambda: (
                        len(self._display_xmlrpc_client.get_display_info())),
                        expected_value=2)
                logging.info('Set mirrored: %s', test_mirrored)
                self._display_xmlrpc_client.set_mirrored(test_mirrored)

                if test_suspend_resume:
                    logging.info('Suspend and resume')
                    self._display_xmlrpc_client.suspend_resume()
                    self._host.wait_up(timeout=20)
                    logging.info('Host is up')

                self.test_display(resolution)
            finally:
                self._chameleon_board.Reset()

        if self._errors:
            raise error.TestError(', '.join(self._errors))

    def get_ext_output_name(self):
        """Gets the first available external output port between Chameleon
        and DUT.

        @return: A tuple (the name of DUT's external output port,
                          the ID of Chameleon connector,
                          the name of Chameleon connector)
        """
        # TODO(waihong): Support multiple connectors.
        for connector_id in self._chameleon_board.ProbeInputs():
            # Plug to ensure the connector is plugged.
            self._chameleon_board.Plug(connector_id)
            connector_name = self._chameleon_board.GetConnectorType(
                    connector_id)
            output = self._display_xmlrpc_client.get_ext_connector_name()
            if output and output.startswith(connector_name):
                return (output, connector_id, connector_name)
        return (None, None, None)

    def set_up_chameleon(self, resolution):
        """Loads the EDID of the given resolution onto Chameleon.

        @param resolution: A tuple of integers (width, height) representing the
                resolution to test.
        """
        logging.info('Setting up %r on port %d (%s)...',
                     resolution, self._connector_id, self._connector_name)

        edid_filename = os.path.join(
                self._test_data_dir, 'edids', '%s_%dx%d' %
                (self._connector_name, resolution[0], resolution[1]))
        if not os.path.exists(edid_filename):
            raise ValueError('EDID file %r does not exist' % edid_filename)

        logging.info('Create edid: %s', edid_filename)
        edid_id = self._chameleon_board.CreateEdid(
                xmlrpclib.Binary(open(edid_filename).read()))

        logging.info('Apply edid %d on port %d (%s)',
                     edid_id, self._connector_id, self._connector_name)
        self._chameleon_board.ApplyEdid(self._connector_id, edid_id)
        self._chameleon_board.DestoryEdid(edid_id)

    @staticmethod
    def parse_ppm(input_file, x, y, width, height, value_bit_mask=8):
        """Parses a PPM image and returns RGB values of pixels.

        @param input_file: The input PPM image.  It is expected to be of binary
                PPM format.
        @param x: The x coordinate to start parsing pixel data.
        @param y: The y coordinate to start parsing pixel data.
        @param width: The width in pixels to parse.
        @param height: The height in pixels to parse.
        @param value_bit_mask: The returned RGB values is truncated to the most
                significant of value_bit_mask bits.

        @return: A 2-dimensional list of RGB value tuples of each pixel.
        """
        with open(input_file) as f:
            input_bytes = f.read()

        input_lines = input_bytes.split('\n', 3)
        ppm_format = input_lines[0].strip()
        if ppm_format != 'P6':
            raise error.TestError('Input PPM image must be of P6 format')
        img_width, img_height = map(int, input_lines[1].strip().split())
        maximum_value = int(input_lines[2].strip())
        pixels = input_lines[3]
        value_bit_length = int(math.ceil(math.log(maximum_value, 2)))
        bytes_per_pixel = 1 if maximum_value < 256 else 2
        bytes_per_raster = img_width * bytes_per_pixel * 3

        discard_lsb = value_bit_length - value_bit_mask
        def _get_pixel(x, y):
            """Get the RGB value of pixel (x, y)."""
            raster = pixels[y * bytes_per_raster:(y + 1) * bytes_per_raster]
            base = x * 6
            rgb_values = struct.unpack(
                    '>HHH', raster[base:base + 3 * bytes_per_pixel])
            if discard_lsb:
                rgb_values = map(lambda v: v >> discard_lsb, rgb_values)
            return tuple(rgb_values)

        results = []
        for w in xrange(0, width):
            results.append([])
            for h in xrange(0, height):
                results[w].append(_get_pixel(x + w, y + h))
        return results

    def test_display(self, resolution):
        """Main display testing logic.

        1. Open a calibration image of the given resolution, and set it to
           fullscreen on the external display.
        2. Capture several regions from the display buffer of Chameleon.
        3. Capture the framebuffer on DUT.
        4. Verify that the captured regions match the content of DUT
           framebuffer.

        @param resolution: A tuple of integers (width, height) representing the
                resolution to test.
        """
        logging.info('Testing %r...', resolution)
        width, height = resolution
        resolution_str = '%dx%d' % (width, height)
        crop_width, crop_height = (40, 40)
        regions_to_test = [
                # Top-left corner.
                (0, 0, crop_width, crop_height),
                # Center.
                (width / 2 - 20, height / 2 - 20, crop_width, crop_height),
                # Bottom-right corner
                (width - 40, height - 40, crop_width, crop_height)
        ]
        chameleon_image_file = (
                'chameleon-%s-%%dx%%d+%%dx%%d.ppm' % resolution_str)
        dut_image_file = 'dut-%s.ppm' % resolution_str

        def _move_cursor():
            """Move mouse cursor to the bottom-left corner."""
            for port in ('eDP1', 'eDP-1'):
                _, edp_h, _, _ = (
                        self._display_xmlrpc_client.get_resolution(port))
                if not edp_h:
                    break
            self._host.run('%s xdotool mousemove %d %d' %
                           (self.X_ENV_VARIABLES, 0, edp_h))

        def _load_calibration_image():
            """Load calibration image from host HTTP server."""
            image_url = ('http://%s:%s' % (self._my_ip, self.HTTPD_PORT) +
                         '/%s.png' % resolution_str)
            self._display_xmlrpc_client.close_tab()
            self._display_xmlrpc_client.load_url(image_url)

        def _save_ppm_image(filename, width, height, pixels):
            """Save as a PPM image."""
            with open(filename, 'w+') as f:
                f.write('P6\n{width} {height}\n1023\n'.format(
                        width=width, height=height))
                for index in xrange(0, len(pixels), 2):
                    pixel = struct.unpack('<H', pixels[index:index + 2])[0]
                    f.write(struct.pack('>H', pixel))

        def _capture_chameleon_fb():
            """Capture Chameleon framebuffer."""
            logging.info('Capturing framebuffer on Chameleon.')
            for r in regions_to_test:
                # XXX: The UART connection is not stable. May result wrong
                # checksum in some cases. So retry if the length not correct.
                for retry in range(3):
                    pixels = self._chameleon_board.DumpPixels(
                            self._connector_id, *r).data
                    pixels_length = len(pixels)
                    if pixels_length == r[2] * r[3] * 6:
                        break
                    else:
                        logging.warn('The length of pixels not correct: %d',
                                     pixels_length)
                # TODO(waihong): Don't save to a file. Directly compare.
                _save_ppm_image(chameleon_image_file % r,
                                r[2], r[3], pixels)

        def _capture_dut_fb():
            """Capture DUT framebuffer."""
            logging.info('Capturing framebuffer on DUT.')
            self._host.run('%s import -window root /tmp/%s' %
                           (self.X_ENV_VARIABLES, dut_image_file))
            self._host.get_file('/tmp/%s' % dut_image_file, os.path.join(
                    self.outputdir, dut_image_file))

        def _verify():
            """Verify that the captured frambuffers match."""
            _, _, fb_x, fb_y = self._display_xmlrpc_client.get_resolution(
                    self._active_output)
            logging.info(
                    'External output framebuffer offset: +%d+%d', fb_x, fb_y)
            for r in regions_to_test:
                # We only capture the selected region from Chameleon.
                chameleon_pixels = self.parse_ppm(
                        os.path.join(self.outputdir, chameleon_image_file % r),
                        0, 0, r[2], r[3])
                # We capture the whole DUT framebuffer. Need to take into
                # account the framebuffer offset of the external output.
                dut_pixels = self.parse_ppm(
                        os.path.join(self.outputdir, dut_image_file),
                        r[0] + fb_x, r[1] + fb_y, r[2], r[3])
                if chameleon_pixels != dut_pixels:
                    error_message = ('%s and %s (%dx%d+%d+%d) mismatch' %
                            (chameleon_image_file % r, dut_image_file,
                             r[2], r[3], r[0] + fb_x, r[1] + fb_y))
                    logging.error(error_message)
                    self._errors.append(error_message)
            self._display_xmlrpc_client.close_tab()

        _move_cursor()
        _load_calibration_image()
        _capture_chameleon_fb()
        _capture_dut_fb()
        _verify()
