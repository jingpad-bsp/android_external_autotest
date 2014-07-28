# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side resolution display test using the Chameleon board."""

import logging
import os
import time
from random import shuffle
from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.chameleon import chameleon_test
from autotest_lib.server.cros.chameleon import edid


class display_ResolutionList(chameleon_test.ChameleonTest):
    """Server side external display test.

    This test iterates the resolution list obtained from the display options
    dialog and verifies that each of them works.
    """

    version = 1
    # Allow a range of pixel value difference.
    PIXEL_DIFF_VALUE_MARGIN = 5
    # Time to wait the calibration image stable, like waiting the info
    # window "DisplayTestExtension triggered full screen" disappeared.
    CALIBRATION_IMAGE_SETUP_TIME = 10
    DEFAULT_TESTCASE_EDID = ('HDMI', 1920, 1080)

    def initialize(self, host):
        super(display_ResolutionList, self).initialize(host)
        self.backup_edid()


    def cleanup(self):
        super(display_ResolutionList, self).cleanup()
        self.restore_edid()

    # TODO: Allow reading testcase_edid from command line.
    def run_once(self, host, test_mirrored=False, testcase_edid=None):
        errors = []
        # (width, height) is the natural resolution for display
        if testcase_edid is None:
            testcase_edid = self.DEFAULT_TESTCASE_EDID
        (tag, width, height) = testcase_edid
        if not self.is_edid_supported(tag, width, height):
            logging.info('skip unsupported EDID: %s_%dx%d', tag, width, height)
            testcase_edid = self.DEFAULT_TESTCASE_EDID

        self.set_up_chameleon((tag, width, height))
        try:
            logging.info('Reconnect output...')
            self.display_client.reconnect_output_and_wait()


            display_info = self.display_client.get_display_info()
            test_display_index = -1

            # get first external and enabled display
            for display_index in xrange(len(display_info)):
                current_display = display_info[display_index]
                if current_display.is_internal:
                    logging.info('Display %d (%s): Internal display, '
                            'skipped.' , display_index,
                            current_display.display_id)
                    continue
                if not current_display.is_enabled:
                    logging.info('Display %d (%s): Disabled display, '
                            'skipped.' , display_index,
                            current_display.display_id)
                    continue

                test_display_index = display_index
                break

            if test_display_index == -1:
                raise RuntimeError("No external display is found.")

            resolutions = self.display_client.get_available_resolutions(
                    test_display_index)
            logging.info('Test display %d (%s): Total %d resolution modes.'
                    '%s', test_display_index, current_display.display_id,
                    len(resolutions),
                    " (Primary)" if current_display.is_primary else "")

            resolution_test_seq = [i for i in xrange(len(resolutions))]
            shuffle(resolution_test_seq)
            logging.info('Set mirrored: %s', test_mirrored)
            self.display_client.set_mirrored(test_mirrored)

            for test_resolution_index in resolution_test_seq:
                # (set_width, set_height) resolution by manual setting
                set_width, set_height = resolutions[
                        test_resolution_index]

                logging.info('Set external display resolution: mode %d,'
                             ' width: %d, height: %d',
                             test_resolution_index, set_width, set_height)
                self.display_client.set_resolution(
                        test_display_index, set_width, set_height)
                logging.info('Waiting the calibration image stable.')

                self.display_client.load_calibration_image ((
                        set_width, set_height))
                self.display_client.hide_cursor()
                time.sleep(self.CALIBRATION_IMAGE_SETUP_TIME)

                logging.info('Checking the resolution.')
                chameleon_resolution = self.chameleon_port.get_resolution()
                dut_resolution = self.display_client.get_resolution()
                # Verify the actual resolution detected by chameleon and
                # dut are the same as what is expected.
                # Note: In mirrored mode, the device may be in hardware
                # mirror (as opposed to software mirror). If so, the
                # actual resolution could be different from the expected
                # one. So we skip the check in mirrored mode.
                if ((set_width, set_height) != chameleon_resolution or
                        (set_width, set_height) != dut_resolution):
                    error_message = (
                            'Detected a different resolution: '
                            'chameleon: %r; dut: %r; expected %r' %
                            (chameleon_resolution, dut_resolution,
                             (set_width, set_height)))
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
