# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side resolution display test using the Chameleon board."""

import logging
import os
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.chameleon import chameleon_test
from autotest_lib.server.cros.chameleon import edid


class display_Resolution(chameleon_test.ChameleonTest):
    """Server side external display test.

    This test talks to a Chameleon board and a DUT to set up, run, and verify
    external display function of the DUT.
    """
    version = 1
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
    # Allow a range of pixel value difference.
    PIXEL_DIFF_VALUE_MARGIN = 5
    # Time to wait the calibration image stable, like waiting the info
    # window "DisplayTestExtension triggered full screen" disappeared.
    CALIBRATION_IMAGE_SETUP_TIME = 10


    def initialize(self, host):
        super(display_Resolution, self).initialize(host)
        self.backup_edid()


    def cleanup(self):
        self.restore_edid()
        super(display_Resolution, self).cleanup()


    def run_once(self, host, test_mirrored=False, test_suspend_resume=False,
                 test_reboot=False):
        errors = []
        for tag, width, height in self.RESOLUTION_TEST_LIST:
            if not self.is_edid_supported(tag, width, height):
                logging.info('skip unsupported EDID: %s_%dx%d', tag, width,
                             height)
                continue

            self.set_up_chameleon((tag, width, height))
            try:
                if test_reboot:
                    logging.info('Reboot...')
                    host.reboot(wait=True)
                    self.display_client.connect()
                else:
                    logging.info('Reconnect output...')
                    self.display_client.reconnect_output_and_wait()

                logging.info('Set mirrored: %s', test_mirrored)
                self.display_client.set_mirrored(test_mirrored)

                if test_suspend_resume:
                    logging.info('Suspend and resume')
                    self.display_client.suspend_resume()
                    if host.wait_up(timeout=20):
                        logging.info('DUT is up')
                    else:
                        raise error.TestError('DUT is not up after resume')

                logging.info('Waiting the calibration image stable.')
                self.display_client.load_calibration_image((width, height))
                self.display_client.hide_cursor()
                time.sleep(self.CALIBRATION_IMAGE_SETUP_TIME)

                logging.info('Checking the resolution.')
                chameleon_resolution = self.chameleon_port.get_resolution()
                dut_resolution = self.chameleon_port.get_resolution()
                # Verify the actual resolution detected by chameleon and dut
                # are the same as what is expected.
                # Note: In mirrored mode, the device may be in hardware mirror
                # (as opposed to software mirror). If so, the actual resolution
                # could be different from the expected one. So we skip the check
                # in mirrored mode.
                if ((width, height) != chameleon_resolution or
                        (width, height) != dut_resolution):
                    error_message = (
                            'Detected a different resolution: '
                            'chameleon: %r; dut: %r; expected %r' %
                            (chameleon_resolution, dut_resolution,
                             (width, height)))
                    if test_mirrored:
                        logging.warn(error_message)
                    else:
                        logging.error(error_message)
                        errors.append(error_message)

                if chameleon_resolution == dut_resolution:
                    error_message = self.check_screen_with_chameleon(
                            '%s-%dx%d' % ((tag,) + dut_resolution),
                            self.PIXEL_DIFF_VALUE_MARGIN, 0)
                    if error_message:
                        errors.append(error_message)

            finally:
                self.display_client.close_tab()

        if errors:
            raise error.TestFail('; '.join(errors))


    def set_up_chameleon(self, resolution):
        """Loads the EDID of the given resolution onto Chameleon.

        @param resolution: A tuple (tag, width, height) representing the
                resolution to test.
        """
        logging.info('Setting up %r on port %d (%s)...',
                     resolution,
                     self.chameleon_port.get_connector_id(),
                     self.chameleon_port.get_connector_type())
        filename = os.path.join(
                self.bindir, 'test_data', 'edids', '%s_%dx%d' % resolution)
        logging.info('Apply edid: %s', filename)
        self.chameleon_port.apply_edid(edid.Edid.from_file(filename))
