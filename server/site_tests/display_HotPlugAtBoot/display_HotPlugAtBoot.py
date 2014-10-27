# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a display hot-plug and reboot test using the Chameleon board."""

import logging

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
        for plugged_before_boot, plugged_after_boot in self.PLUG_CONFIGS:
            logging.info('TESTING THE CASE: %s > reboot > %s',
                         'plug' if plugged_before_boot else 'unplug',
                         'plug' if plugged_after_boot else 'unplug')
            boot_id = host.get_boot_id()
            self.set_plug(plugged_before_boot)

            # Don't wait DUT up. Do plug/unplug while booting.
            self.reboot(wait=False)

            host.test_wait_for_shutdown()
            self.set_plug(plugged_after_boot)
            host.test_wait_for_boot(boot_id)

            self.display_client.connect()
            self.check_external_display_connector(
                    expected_connector if plugged_after_boot else False)

            if plugged_after_boot:
                if test_mirrored and not self.is_mirrored_enabled():
                    error_message = 'Error: not rebooted to mirrored mode'
                    errors.append(error_message)
                    logging.error(error_message)
                    self.set_mirrored(True)
                else:
                    test_name = 'SCREEN-%dx%d-%c-B-P' % (
                            width, height, 'P' if plugged_before_boot else 'U')
                    self.load_test_image_and_check(
                            test_name, resolution,
                            under_mirrored_mode=test_mirrored,
                            error_list=errors)

        self.raise_on_errors(errors)
