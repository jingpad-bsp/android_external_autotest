# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side resolution display test using the Chameleon board."""

import logging
import os
import re
import time
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
    CALIBRATION_IMAGE_SETUP_TIME = 10
    PIXEL_DIFF_MARGIN = 1
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

    def test_display(self, resolution):
        """Main display testing logic.

        1. Open a calibration image of the given resolution, and set it to
           fullscreen on the external display.
        2. Capture the whole screen from the display buffer of Chameleon.
        3. Capture the framebuffer on DUT.
        4. Verify that the captured screen match the content of DUT
           framebuffer.

        @param resolution: A tuple of integers (width, height) representing the
                resolution to test.
        """
        logging.info('Testing %r...', resolution)
        width, height = resolution
        resolution_str = '%dx%d' % (width, height)
        chameleon_image_file = 'chameleon-%s.bgra' % resolution_str
        dut_image_file = 'dut-%s.bgra' % resolution_str

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
            logging.info('Waiting the calibration image stable.')
            image_url = ('http://%s:%s' % (self._my_ip, self.HTTPD_PORT) +
                         '/%s.png' % resolution_str)
            self._display_xmlrpc_client.close_tab()
            self._display_xmlrpc_client.load_url(image_url)
            time.sleep(self.CALIBRATION_IMAGE_SETUP_TIME)

        def _capture_chameleon_fb():
            """Capture Chameleon framebuffer."""
            logging.info('Capturing framebuffer on Chameleon.')
            pixels = self._chameleon_board.DumpPixels(self._connector_id).data
            # Write to file for debug.
            file_path = os.path.join(self.outputdir, chameleon_image_file)
            open(file_path, 'w+').write(pixels)
            return pixels

        def _capture_dut_fb():
            """Capture DUT framebuffer."""
            logging.info('Capturing framebuffer on DUT.')
            _, _, fb_x, fb_y = self._display_xmlrpc_client.get_resolution(
                    self._active_output)
            local_path = os.path.join(self.outputdir, dut_image_file)
            remote_path = os.path.join('/tmp', dut_image_file)
            command = ('%s import -window root -depth 8 -crop %dx%d+%d+%d %s' %
                       (self.X_ENV_VARIABLES, width, height, fb_x, fb_y,
                        remote_path))
            self._host.run(command)
            self._host.get_file(remote_path, local_path)
            return open(local_path).read()

        def _remove_image_files():
            chameleon_path = os.path.join(self.outputdir, chameleon_image_file)
            dut_path = os.path.join(self.outputdir, dut_image_file)
            for file_path in (chameleon_path, dut_path):
                os.remove(file_path)

        def _verify():
            chameleon_pixels = _capture_chameleon_fb()
            chameleon_pixels_len = len(chameleon_pixels)
            dut_pixels = _capture_dut_fb()
            dut_pixels_len = len(dut_pixels)

            if chameleon_pixels_len != dut_pixels_len:
                error_message = ('Lengths of pixels not the same: %d != %d' %
                        (chameleon_pixels_len, dut_pixels_len))
                logging.error(error_message)
                self._errors.append(error_message)
                return

            logging.info('Comparing the pixels...')
            for i in xrange(len(dut_pixels)):
                chameleon_pixel = ord(chameleon_pixels[i])
                dut_pixel = ord(dut_pixels[i])
                # Skip the fourth byte, i.e. the alpha value.
                if (i % 4 != 3 and abs(chameleon_pixel - dut_pixel) >
                        self.PIXEL_DIFF_MARGIN):
                    error_message = ('The pixel, offset %d, on '
                            'resolution %s, not match: %d != %d' %
                            (i, resolution_str, chameleon_pixel, dut_pixel))
                    logging.error(error_message)
                    self._errors.append(error_message)
                    break
            else:
                logging.info('All pixels match.')
                _remove_image_files()

        def _cleanup():
            self._display_xmlrpc_client.close_tab()

        _move_cursor()
        _load_calibration_image()
        _verify()
        _cleanup()
