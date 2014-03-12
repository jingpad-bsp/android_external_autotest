# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a display hot-plug and suspend test using the Chameleon board."""

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.chameleon import chameleon_test


class display_HotPlugAtSuspend(chameleon_test.ChameleonTest):
    """Display hot-plug and suspend test.

    This test talks to a Chameleon board and a DUT to set up, run, and verify
    DUT behavior response to different configuration of hot-plug during
    suspend/resume.
    """
    version = 1
    PLUG_CONFIGS = [
        # (plugged_before_suspend, plugged_after_suspend, plugged_before_resume)
        (True, True, True),
        (True, False, False),
        (True, False, True),
        (False, True, True),
        (False, True, False),
    ]
    # Duration of suspend, in second.
    SUSPEND_DURATION = 15
    # Time for the transition of suspend.
    SUSPEND_TRANSITION_TIME = 2
    # Time margin to do plug/unplug before resume.
    TIME_MARGIN_BEFORE_RESUME = 5
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
        for (plugged_before_suspend, plugged_after_suspend,
             plugged_before_resume) in self.PLUG_CONFIGS:
            logging.info('TESTING THE CASE: %s > suspend > %s > %s > resume',
                         'plug' if plugged_before_suspend else 'unplug',
                         'plug' if plugged_after_suspend else 'unplug',
                         'plug' if plugged_before_resume else 'unplug')
            boot_id = host.get_boot_id()
            if plugged_before_suspend:
                self.chameleon_port.plug()
            else:
                self.chameleon_port.unplug()

            logging.info('Going to suspend, for %d seconds...',
                         self.SUSPEND_DURATION)
            time_before_suspend = time.time()
            self.display_client.suspend_resume_bg(self.SUSPEND_DURATION)

            # Confirm DUT suspended.
            logging.info('- Wait for sleep...')
            time.sleep(self.SUSPEND_TRANSITION_TIME)
            host.test_wait_for_sleep()
            if plugged_after_suspend:
                self.chameleon_port.plug()
            else:
                self.chameleon_port.unplug()

            current_time = time.time()
            sleep_time = (self.SUSPEND_DURATION -
                          (current_time - time_before_suspend) -
                          self.TIME_MARGIN_BEFORE_RESUME)
            logging.info('- Sleep for %.2f seconds...', sleep_time)
            time.sleep(sleep_time)
            if plugged_before_resume:
                self.chameleon_port.plug()
            else:
                self.chameleon_port.unplug()
            time.sleep(self.TIME_MARGIN_BEFORE_RESUME)

            logging.info('- Wait for resume...')
            host.test_wait_for_resume(boot_id)

            logging.info('Resumed back')
            current_connector = self.display_client.get_connector_name()
            # Check the DUT behavior: see the external display?
            if plugged_before_resume:
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
                        'SCREEN-%dx%d-%c-S-%c-P-R' % (
                             width, height,
                             'P' if plugged_before_suspend else 'U',
                             'P' if plugged_after_suspend else 'U'),
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
