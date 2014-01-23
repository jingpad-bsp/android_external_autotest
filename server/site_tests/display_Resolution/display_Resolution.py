# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side resolution display test using the Chameleon board."""

import logging
import operator
import os
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server import test
from autotest_lib.server.cros.chameleon import display_client

# pylint: disable=E1101

class display_Resolution(test.test):
    """Server side external display test.

    This test talks to a Chameleon board and a DUT to set up, run, and verify
    external display function of the DUT.
    """
    version = 1
    CALIBRATION_IMAGE_SETUP_TIME = 10

    # Allow a range of pixel value difference.
    PIXEL_DIFF_VALUE_MARGIN = 5
    # Allow a number of pixels not matched, caused by the cursor.
    TOTAL_WRONG_PIXELS_MARGIN = 20

    RESOLUTION_TEST_LIST = [
            # Mix DP and HDMI together to test the converter cases.
            ('DP', 1280, 800),
            ('DP', 1440, 900),
            ('DP', 1600, 900),
            ('DP', 1680, 1050),
            ('DP', 1920, 1080),
            ('HDMI', 1280, 720),
            ('HDMI', 1920, 1080),
    ]

    def initialize(self, host):
        self._errors = []
        self._host = host
        self._test_data_dir = os.path.join(
                self.bindir, 'display_Resolution_test_data')
        self._display_client = display_client.DisplayClient(host)
        self._display_client.initialize(self._test_data_dir)
        self._chameleon = host.chameleon
        self._chameleon_port = None

    def cleanup(self):
        if self._display_client:
            self._display_client.cleanup()

    def run_once(self, host, usb_serial=None, test_mirrored=False,
                 test_suspend_resume=False):
        self._chameleon_port = self.get_connected_port()
        if self._chameleon_port is None:
            raise error.TestError('DUT and Chameleon board not connected')

        for tag, width, height in self.RESOLUTION_TEST_LIST:
            try:
                self.set_up_chameleon((tag, width, height))
                logging.info('Reconnect output...')
                self._display_client.reconnect_output_and_wait()
                logging.info('Set mirrored: %s', test_mirrored)
                self._display_client.set_mirrored(test_mirrored)

                if test_suspend_resume:
                    logging.info('Suspend and resume')
                    self._display_client.suspend_resume()
                    if self._host.wait_up(timeout=20)
                        logging.info('DUT is up')
                    else:
                        raise error.TestError('DUT is not up after resume')

                logging.info('Waiting the calibration image stable.')
                self._display_client.load_calibration_image((width, height))
                self._display_client.move_cursor_to_bottom_right()
                time.sleep(self.CALIBRATION_IMAGE_SETUP_TIME)

                self.check_screen_with_chameleon(
                        '%s-%dx%d' % (tag, width, height),
                        self.PIXEL_DIFF_VALUE_MARGIN,
                        self.TOTAL_WRONG_PIXELS_MARGIN)
            finally:
                self._display_client.close_tab()
                self._chameleon.reset()

        if self._errors:
            raise error.TestError(', '.join(self._errors))

    def get_connected_port(self):
        """Gets the first connected output port between Chameleon and DUT.

        @return: A ChameleonPort object.
        """
        # TODO(waihong): Support multiple connectors.
        for chameleon_port in self._chameleon.get_all_ports():
            # Plug to ensure the connector is plugged.
            chameleon_port.plug()
            connector_type = chameleon_port.get_connector_type()
            output = self._display_client.get_connector_name()
            # TODO(waihong): Make sure eDP work in this way.
            if output and output.startswith(connector_type):
                return chameleon_port
        return None

    def set_up_chameleon(self, resolution):
        """Loads the EDID of the given resolution onto Chameleon.

        @param resolution: A tuple (tag, width, height) representing the
                resolution to test.
        """
        logging.info('Setting up %r on port %d (%s)...',
                     resolution,
                     self._chameleon_port.get_connector_id(),
                     self._chameleon_port.get_connector_type())
        edid_filename = os.path.join(
                self._test_data_dir, 'edids', '%s_%dx%d' % resolution)
        if not os.path.exists(edid_filename):
            raise ValueError('EDID file %r does not exist' % edid_filename)

        logging.info('Apply edid: %s', edid_filename)
        self._chameleon_port.apply_edid(open(edid_filename).read())

    def check_screen_with_chameleon(self,
            tag, pixel_diff_value_margin=0, total_wrong_pixels_margin=0):
        """Checks the DUT external screen with Chameleon.

        1. Capture the whole screen from the display buffer of Chameleon.
        2. Capture the framebuffer on DUT.
        3. Verify that the captured screen match the content of DUT framebuffer.

        @param tag: A string of tag for the prefix of output filenames.
        @param pixel_diff_value_margin: The margin for comparing a pixel. Only
                if a pixel difference exceeds this margin, will treat as a wrong
                pixel.
        @param total_wrong_pixels_margin: The margin for the number of wrong
                pixels. If the total number of wrong pixels exceeds this margin,
                the check fails.

        @return: True if the check passed; otherwise False.
        """
        logging.info('Checking screen with Chameleon (tag: %s)...', tag)
        chameleon_path = os.path.join(self.outputdir, '%s-chameleon.bgra' % tag)
        dut_path = os.path.join(self.outputdir, '%s-dut.bgra' % tag)

        logging.info('Capturing framebuffer on Chameleon.')
        chameleon_pixels = self._chameleon_port.capture_screen(chameleon_path)
        chameleon_pixels_len = len(chameleon_pixels)

        logging.info('Capturing framebuffer on DUT.')
        dut_pixels = self._display_client.capture_external_screen(dut_path)
        dut_pixels_len = len(dut_pixels)

        if chameleon_pixels_len != dut_pixels_len:
            message = ('Result of %s: lengths of pixels not match: %d != %d' %
                    (tag, chameleon_pixels_len, dut_pixels_len))
            logging.error(message)
            self._errors.append(message)
            return

        logging.info('Comparing the pixels...')
        total_wrong_pixels = 0
        # The dut_pixels array are formatted in BGRA.
        for i in xrange(0, len(dut_pixels), 4):
            # Skip the fourth byte, i.e. the alpha value.
            chameleon_pixel = tuple(ord(p) for p in chameleon_pixels[i:i+3])
            dut_pixel = tuple(ord(p) for p in dut_pixels[i:i+3])
            # Compute the maximal difference for a pixel.
            diff_value = max(map(abs, map(
                    operator.sub, chameleon_pixel, dut_pixel)))
            if (diff_value > pixel_diff_value_margin):
                if total_wrong_pixels == 0:
                    first_pixel_message = ('offset %d, %r != %r' %
                            (i, chameleon_pixel, dut_pixel))
                total_wrong_pixels += 1

        if total_wrong_pixels > 0:
            message = ('Result of %s: total %d wrong pixels, e.g. %s' %
                    (tag, total_wrong_pixels, first_pixel_message))
            if total_wrong_pixels > total_wrong_pixels_margin:
                logging.error(message)
                self._errors.append(message)
            else:
                logging.warn(message)
        else:
            logging.info('Result of %s: all pixels match', tag)
            for file_path in (chameleon_path, dut_path):
                os.remove(file_path)
