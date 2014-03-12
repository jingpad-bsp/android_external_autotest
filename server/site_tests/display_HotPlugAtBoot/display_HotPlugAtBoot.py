# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a display hot-plug and reboot test using the Chameleon board."""

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.chameleon import chameleon_test


class display_HotPlugAtBoot(chameleon_test.ChameleonTest):
    """Display hot-plug and reboot test.

    This test talks to a Chameleon board and a DUT to set up, run, and verify
    DUT behavior response to different configuration of hot-plug during boot.
    """
    version = 1
    PLUG_CONFIGS = [
        # (plugged_before_boot, plugged_after_boot)
        (False, True),
        (True, True),
        (True, False),
    ]
    # Allow a range of pixel value difference.
    PIXEL_DIFF_VALUE_MARGIN = 5
    # Time to wait the calibration image stable, like waiting the info
    # window "DisplayTestExtension triggered full screen" disappeared.
    CALIBRATION_IMAGE_SETUP_TIME = 10


    def run_once(self, host, test_mirrored=False):
        width, height = self.chameleon_port.get_resolution()
        logging.info('See the display on Chameleon: port %d (%s) %dx%d',
                     self.chameleon_port.get_connector_id(),
                     self.chameleon_port.get_connector_type(),
                     width, height)
        # Keep the original connector name, for later comparison.
        expected_connector = self.display_client.get_connector_name()
        logging.info('See the display on DUT: %s', expected_connector)

        logging.info('Set mirrored: %s', test_mirrored)
        self.display_client.set_mirrored(test_mirrored)

        errors = []
        for plugged_before_boot, plugged_after_boot in self.PLUG_CONFIGS:
            logging.info('TESTING THE CASE: %s > reboot > %s',
                         'plug' if plugged_before_boot else 'unplug',
                         'plug' if plugged_after_boot else 'unplug')
            boot_id = host.get_boot_id()
            if plugged_before_boot:
                self.chameleon_port.plug()
            else:
                self.chameleon_port.unplug()

            # Don't wait DUT up. Do plug/unplug while booting.
            host.reboot(wait=False)
            host.test_wait_for_shutdown()
            if plugged_after_boot:
                self.chameleon_port.plug()
            else:
                self.chameleon_port.unplug()

            host.test_wait_for_boot(boot_id)
            self.display_client.connect()
            current_connector = self.display_client.get_connector_name()
            # Check the DUT behavior: see the external display?
            if plugged_after_boot:
                if not current_connector:
                    raise error.TestFail('Failed to see the external display')
                elif current_connector != expected_connector:
                    raise error.TestFail(
                            'See a different display: %s != %s' %
                            (current_connector, expected_connector))

                logging.info('Waiting the calibration image stable.')
                self.display_client.load_calibration_image((width, height))
                self.display_client.hide_cursor()
                time.sleep(self.CALIBRATION_IMAGE_SETUP_TIME)

                error_message = self.check_screen_with_chameleon(
                        'SCREEN-%dx%d-%c-B-P' % (
                             width, height,
                             'P' if plugged_before_boot else 'U'),
                        self.PIXEL_DIFF_VALUE_MARGIN, 0)
                if error_message:
                    errors.append(error_message)
            else:
                if current_connector:
                    raise error.TestFail(
                            'See a not-expected external display: %s' %
                             current_connector)

        if errors:
            raise error.TestFail('; '.join(errors))
