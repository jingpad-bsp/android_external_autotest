# Copyright 2014 The Chromium OS Authors. All rights reserved.
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
    # Allowed timeout for the transition of suspend.
    SUSPEND_TIMEOUT = 10
    # Allowed timeout for the transition of resume.
    RESUME_TIMEOUT = 20
    # Time margin to do plug/unplug before resume.
    TIME_MARGIN_BEFORE_RESUME = 5


    def run_once(self, host, test_mirrored=False):
        logging.info('See the display on Chameleon: port %d (%s)',
                     self.chameleon_port.get_connector_id(),
                     self.chameleon_port.get_connector_type())

        logging.info('Set mirrored: %s', test_mirrored)
        self.display_facade.set_mirrored(test_mirrored)

        # Keep the original connector name, for later comparison.
        expected_connector = self.display_facade.get_external_connector_name()
        resolution = self.display_facade.get_external_resolution()
        logging.info('See the display on DUT: %s (%dx%d)', expected_connector,
                     *resolution)

        errors = []
        for (plugged_before_suspend, plugged_after_suspend,
             plugged_before_resume) in self.PLUG_CONFIGS:
            logging.info('TESTING THE CASE: %s > suspend > %s > %s > resume',
                         'plug' if plugged_before_suspend else 'unplug',
                         'plug' if plugged_after_suspend else 'unplug',
                         'plug' if plugged_before_resume else 'unplug')
            boot_id = host.get_boot_id()
            self.chameleon_port.set_plug(plugged_before_suspend)
            if test_mirrored:
                # magic sleep to make nyan_big wake up in mirrored mode
                # TODO: find root cause
                time.sleep(6)
            logging.info('Going to suspend, for %d seconds...',
                         self.SUSPEND_DURATION)
            time_before_suspend = time.time()
            self.display_facade.suspend_resume_bg(self.SUSPEND_DURATION)

            # Confirm DUT suspended.
            logging.info('- Wait for sleep...')
            host.test_wait_for_sleep(self.SUSPEND_TIMEOUT)
            self.chameleon_port.set_plug(plugged_after_suspend)

            current_time = time.time()
            sleep_time = (self.SUSPEND_DURATION -
                          (current_time - time_before_suspend) -
                          self.TIME_MARGIN_BEFORE_RESUME)
            if sleep_time > 0:
                logging.info('- Sleep for %.2f seconds...', sleep_time)
                time.sleep(sleep_time)
            self.chameleon_port.set_plug(plugged_before_resume)
            time.sleep(self.TIME_MARGIN_BEFORE_RESUME)

            logging.info('- Wait for resume...')
            self.host.test_wait_for_resume(boot_id, self.RESUME_TIMEOUT)

            logging.info('Resumed back')

            self.check_external_display_connector(expected_connector
                    if plugged_before_resume else False)
            if plugged_before_resume:
                if test_mirrored and (
                        not self.display_facade.is_mirrored_enabled()):
                    error_message = 'Error: not resumed to mirrored mode'
                    errors.append(error_message)
                    logging.error(error_message)
                    logging.info('Set mirrored: %s', True)
                    self.display_facade.set_mirrored(True)
                else:
                    self.screen_test.test_screen_with_image(
                            resolution, test_mirrored, errors)

        if errors:
            raise error.TestFail('; '.join(set(errors)))
