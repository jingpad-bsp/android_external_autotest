# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side to enable HDCP and verify screen."""

import logging

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.chameleon import chameleon_port_finder
from autotest_lib.client.cros.chameleon import chameleon_screen_test
from autotest_lib.server import test
from autotest_lib.server.cros.multimedia import remote_facade_factory


class display_HDCPScreen(test.test):
    """Server side test to enable HDCP and verify screen.

    This test forces CrOS to enable HDCP and compares screens between CrOS
    and Chameleon.
    """
    version = 1

    def run_once(self, host, test_mirrored=False):
        if host.get_architecture() != 'arm':
            raise error.TestNAError('HDCP is not supported on a non-ARM device')

        factory = remote_facade_factory.RemoteFacadeFactory(host)
        display_facade = factory.create_display_facade()
        chameleon_board = host.chameleon

        chameleon_board.reset()
        finder = chameleon_port_finder.ChameleonVideoInputFinder(
                chameleon_board, display_facade)

        errors = []
        for chameleon_port in finder.iterate_all_ports():
            screen_test = chameleon_screen_test.ChameleonScreenTest(
                    chameleon_port, display_facade, self.outputdir)

            logging.info('See the display on Chameleon: port %d (%s)',
                         chameleon_port.get_connector_id(),
                         chameleon_port.get_connector_type())

            logging.info('Set mirrored: %s', test_mirrored)
            display_facade.set_mirrored(test_mirrored)

            resolution = display_facade.get_external_resolution()
            logging.info('Detected resolution on CrOS: %dx%d', *resolution)

            display_facade.set_content_protection('Desired')
            try:
                state = utils.wait_for_value(
                        display_facade.get_content_protection, 'Enabled')
                if state != 'Enabled':
                    error_message = 'Failed to enable HDCP, state: %r' % state
                    logging.error(error_message)
                    errors.append(error_message)
                    continue

                logging.info('Test screen under HDCP enabled...')
                screen_test.test_screen_with_image(
                        resolution, test_mirrored, errors)
            finally:
                display_facade.set_content_protection('Undesired')

            state = utils.wait_for_value(
                    display_facade.get_content_protection, 'Undesired')
            assert state == 'Undesired'

            logging.info('Test screen under HDCP disabled...')
            screen_test.test_screen_with_image(
                    resolution, test_mirrored, errors)

        if errors:
            raise error.TestFail('; '.join(set(errors)))
