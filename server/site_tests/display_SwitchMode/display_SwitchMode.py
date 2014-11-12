# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is test switching the external display mode."""

import logging, time

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
        test_name = '%s-%s-%s' % (self.connector_used,
            str(resolution),
            'mirrored' if test_mirrored else 'extended')
        # Check connector
        self.check_external_display_connector(self.connector_used)
        # Check test image
        self.load_test_image_and_check(
            test_name, resolution,
            under_mirrored_mode=test_mirrored,
            error_list=self.errors)
        self.raise_on_errors(self.errors)


    def set_mode_and_check(self, test_mirrored):
        """Sets display mode and checks status

        @param test_mirrored: is mirrored mode active

        """
        self.set_mirrored(test_mirrored)
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
