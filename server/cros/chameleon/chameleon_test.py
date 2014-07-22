# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from PIL import Image
from PIL import ImageChops

from autotest_lib.client.common_lib import error
from autotest_lib.server import test
from autotest_lib.server.cros.chameleon import display_client


def _unlevel(p):
    """Unlevel a color value from TV level back to PC level

    @param p: The color value in one character byte

    @return: The color value in integer in PC level
    """
    # TV level: 16~236; PC level: 0~255
    p = (p - 126) * 128 / 110 + 128
    if p < 0:
        p = 0
    elif p > 255:
        p = 255
    return p


class ChameleonTest(test.test):
    """This is the base class of Chameleon tests.

    This base class initializes Chameleon board and its related services,
    like connecting Chameleond and DisplayClient. Also kills the connections
    on cleanup.
    """

    _TIMEOUT_VIDEO_STABLE_PROBE = 10


    def initialize(self, host):
        """Initializes.

        @param host: The Host object of DUT.
        """
        self.display_client = display_client.DisplayClient(host)
        self.display_client.initialize()
        self.chameleon = host.chameleon
        self.chameleon_port = self._get_connected_port()
        if self.chameleon_port is None:
            raise error.TestError('DUT and Chameleon board not connected')
        self._platform_prefix = host.get_platform().lower().split('_')[0]
        self._unlevel_func = None
        if self._platform_prefix in ('snow', 'spring', 'skate', 'peach'):
            self._unlevel_func =  _unlevel


    def is_edid_supported(self, tag, width, height):
        """Check whether the EDID is supported by DUT

        @param tag: The tag of the EDID file; 'HDMI' or 'DP'
        @param width: The screen width
        @param height: The screen height

        @return: True if the check passes; False otherwise.
        """
        # TODO: This is a quick workaround; some of our arm devices so far only
        # support the HDMI EDIDs and the DP one at 1680x1050. A more proper
        # solution is to build a database of supported resolutions and pixel
        # clocks for each model and check if the EDID is in the supported list.
        if self._platform_prefix in ('snow', 'spring', 'skate', 'peach'):
            if tag == 'DP':
                return width == 1680 and height == 1050
        return True


    def backup_edid(self):
        """Backups the original EDID."""
        self._original_edid = self.chameleon_port.read_edid()
        self._original_edid_path = os.path.join(self.outputdir, 'original_edid')
        self._original_edid.to_file(self._original_edid_path)


    def restore_edid(self):
        "Restores the original EDID."""
        if (hasattr(self, 'chameleon_port') and self.chameleon_port and
                hasattr(self, '_original_edid') and self._original_edid):
            current_edid = self.chameleon_port.read_edid()
            if self._original_edid.data != current_edid.data:
                logging.info('Restore the original EDID...')
                self.chameleon_port.apply_edid(self._original_edid)
                # Remove the original EDID file after restore.
                os.remove(self._original_edid_path)


    def cleanup(self):
        """Cleans up."""
        if hasattr(self, 'display_client') and self.display_client:
            self.display_client.cleanup()

        if hasattr(self, 'chameleon') and self.chameleon:
          retry_count = 2
          while not self.chameleon.is_healthy() and retry_count >= 0:
              logging.info('Chameleon is not healthy. Try to repair it... '
                           '(%d retrys left)', retry_count)
              self.chameleon.repair()
              retry_count = retry_count - 1
          if self.chameleon.is_healthy():
              logging.info('Chameleon is healthy.')
          else:
              logging.warning('Chameleon is not recovered after repair.')

        # Unplug the Chameleon port, not to affect other test cases.
        if hasattr(self, 'chameleon_port') and self.chameleon_port:
            self.chameleon_port.unplug()


    def _get_connected_port(self):
        """Gets the first connected output port between Chameleon and DUT.

        @return: A ChameleonPort object.
        """
        self.chameleon.reset()
        # TODO(waihong): Support multiple connectors.
        for chameleon_port in self.chameleon.get_all_ports():
            connector_type = chameleon_port.get_connector_type()
            # Plug to ensure the connector is plugged.
            chameleon_port.plug()
            # Don't care about video input stable in the end or timeout.
            # It will be checked on the matching of the connect names.
            chameleon_port.wait_video_input_stable(
                    self._TIMEOUT_VIDEO_STABLE_PROBE)
            output = self.display_client.get_connector_name()

            # TODO(waihong): Make sure eDP work in this way.
            if output and output.startswith(connector_type):
                return chameleon_port
            # Unplug the port if it is not the connected.
            chameleon_port.unplug()
        return None


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

        @return: None if the check passes; otherwise, a string of error message.
        """
        logging.info('Checking screen with Chameleon (tag: %s).', tag)
        logging.info('Capturing framebuffer on Chameleon...')
        chameleon_image = self.chameleon_port.capture_screen()
        if self._unlevel_func:
            chameleon_image = Image.eval(chameleon_image, self._unlevel_func)
        logging.info('Capturing framebuffer on DUT...')
        dut_image = self.display_client.capture_external_screen()

        if chameleon_image.size != dut_image.size:
            message = ('Result of %s: lengths of screen not match: %d != %d' %
                    (tag, chameleon_image.size, dut_image.size))
            logging.error(message)
            return message

        logging.info('Comparing the images...')
        diff_image = ImageChops.difference(chameleon_image, dut_image)
        histogram = diff_image.convert('L').histogram()
        total_wrong_pixels = sum(histogram[pixel_diff_value_margin + 1:])

        if total_wrong_pixels > 0:
            message = ('Result of %s: total %d wrong pixels' %
                       (tag, total_wrong_pixels))
            if total_wrong_pixels > total_wrong_pixels_margin:
                logging.error(message)
                return message
            else:
                message += (', within the acceptable range %d' %
                            total_wrong_pixels_margin)
                logging.warning(message)
            logging.debug('Histogram: %r', histogram)
            chameleon_image.save(os.path.join(self.outputdir,
                                              '%s-chameleon.png' % tag))
            dut_image.save(os.path.join(self.outputdir, '%s-dut.png' % tag))
        else:
            logging.info('Result of %s: all pixels match', tag)
        return None
