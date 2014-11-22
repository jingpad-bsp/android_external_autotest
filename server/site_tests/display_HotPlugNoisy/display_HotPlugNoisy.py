# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This test remotely emulates noisy HPD line when connecting to an external
display in extended mode using the Chameleon board."""

import logging
import time
from autotest_lib.server.cros.chameleon import chameleon_test


class display_HotPlugNoisy(chameleon_test.ChameleonTest):
    """Noisy display HPD test.

    This test talks to a Chameleon board and a DUT to set up, run, and verify
    DUT behavior in response to noisy HPD line.
    """
    version = 1
    PLUG_CONFIGS = [
        # (plugged_before_noise, plugged_after_noise)

        (False, False),
        (False, True),
        (True, False),
        (True, True),
    ]

    # pulse segments in msec that end with plugged state
    PULSES_PLUGGED = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024]
    # pulse segments in msec that end with unplugged state
    PULSES_UNPLUGGED = PULSES_PLUGGED + [2048]


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
        for (plugged_before_noise, plugged_after_noise) in self.PLUG_CONFIGS:
            logging.info('TESTING THE CASE: %s > noise > %s',
                         'plug' if plugged_before_noise else 'unplug',
                         'plug' if plugged_after_noise else 'unplug')

            self.chameleon_port.set_plug(plugged_before_noise)

            self.check_external_display_connector(
                    expected_connector if plugged_before_noise else False)

            self.chameleon_port.fire_mixed_hpd_pulses(
                    self.PULSES_PLUGGED if plugged_after_noise
                                        else self.PULSES_UNPLUGGED)

            self.check_external_display_connector(
                    expected_connector if plugged_after_noise else False)

            if plugged_after_noise:
                self.screen_test.test_screen_with_image(
                        resolution, test_mirrored, errors)
            else:
                time.sleep(1)

        self.raise_on_errors(errors)
