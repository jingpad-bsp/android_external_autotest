# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This test remotely emulates noisy HPD line when connecting to an external
display in extended mode using the Chameleon board."""

import logging
from autotest_lib.server.cros.chameleon import chameleon_test


class display_HotPlugNoisy(chameleon_test.ChameleonTest):
    """Noisy display HPD test.

    This test talks to a Chameleon board and a DUT to set up, run, and verify
    DUT behavior in response to noisy HPD line.
    """
    version = 1
    PLUG_CONFIGS = [
        # (pulse_width_us, pulse_count, plugged_before_noise,
        #  plugged_after_noise)

        (100, 10000, False, False),
        (100, 10000, False, True),
        (100, 10000, True, False),
        (100, 10000, True, True),
        (1, 1000000, True, True),
    ]


    def run_once(self, host, test_mirrored=False):
        width, height = resolution = self.chameleon_port.get_resolution()
        logging.info('See the display on Chameleon: port %d (%s) %dx%d',
                     self.chameleon_port.get_connector_id(),
                     self.chameleon_port.get_connector_type(),
                     width, height)
        # Keep the original connector name, for later comparison.
        expected_connector = self.display_client.get_external_connector_name()
        logging.info('See the display on DUT: %s', expected_connector)

        self.set_mirrored(test_mirrored)
        errors = []
        for (pulse_width_us, pulse_count, plugged_before_noise,
                plugged_after_noise) in self.PLUG_CONFIGS:
            logging.info('TESTING THE CASE: %s > noise > %s',
                         'plug' if plugged_before_noise else 'unplug',
                         'plug' if plugged_after_noise else 'unplug')

            self.set_plug(plugged_before_noise)

            self.check_external_display_connector(
                    expected_connector if plugged_before_noise else None)

            self.chameleon_port.fire_hpd_pulse(pulse_width_us, repeat_count=
                    pulse_count, end_level=plugged_after_noise)

            self.check_external_display_connector(
                    expected_connector if plugged_after_noise else None)

            if plugged_after_noise:
                test_name = 'SCREEN-%dx%d-%c-N-P' % (
                        width, height, 'P' if plugged_before_noise else 'U')
                self.load_test_image_and_check(
                        test_name, resolution,
                        under_mirrored_mode=test_mirrored, error_list=errors)

        self.raise_on_errors(errors)
