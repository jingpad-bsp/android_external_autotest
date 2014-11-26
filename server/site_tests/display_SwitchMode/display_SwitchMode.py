# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is test switching the external display mode."""

import logging, time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.chameleon import chameleon_test


class display_SwitchMode(chameleon_test.ChameleonTest):
    """External Display switch between extended and mirrored modes.

    This test switches the external display mode between extended
    and mirrored modes, and checks resolution and static test image.
    """
    version = 1
    WAIT_AFTER_SWITCH = 5

    def check_external_display(self, test_mirrored):
        """Display status check

        @param test_mirrored: is mirrored mode active

        """
        resolution = self.display_facade.get_external_resolution()
        # Check connector
        self.check_external_display_connector(self.connector_used)
        # Check test image
        self.screen_test.test_screen_with_image(
                resolution, test_mirrored, self.errors)
        if self.errors:
            raise error.TestFail('; '.join(set(self.errors)))


    def set_mode_and_check(self, test_mirrored):
        """Sets display mode and checks status

        @param test_mirrored: is mirrored mode active

        """
        logging.info('Set mirrored: %s', test_mirrored)
        self.display_facade.set_mirrored(test_mirrored)
        time.sleep(self.WAIT_AFTER_SWITCH)
        self.check_external_display(test_mirrored)


    def run_once(self, host, repeat):
        self.errors = list()
        logging.debug('See the display on Chameleon: port %d (%s)',
                     self.chameleon_port.get_connector_id(),
                     self.chameleon_port.get_connector_type())
        # Keep the original connector name, for later comparison.
        self.connector_used = self.display_facade.get_external_connector_name()

        for i in xrange(repeat):
            logging.info("Iteration %d", (i + 1))
            self.set_mode_and_check(False)
            self.set_mode_and_check(True)
