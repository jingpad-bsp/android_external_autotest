# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side resolution display test using the Chameleon board."""

import logging
import os

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.chameleon import chameleon_port_finder
from autotest_lib.client.cros.chameleon import chameleon_screen_test
from autotest_lib.client.cros.chameleon import edid
from autotest_lib.server import test
from autotest_lib.server.cros.multimedia import remote_facade_factory


class display_ResolutionList(test.test):
    """Server side external display test.

    This test iterates the resolution list obtained from the display options
    dialog and verifies that each of them works.
    """

    version = 1
    DEFAULT_TESTCASE_SPEC = ('HDMI', 1920, 1080)

    # TODO: Allow reading testcase_spec from command line.
    def run_once(self, host, test_mirrored=False, testcase_spec=None):
        if testcase_spec is None:
            testcase_spec = self.DEFAULT_TESTCASE_SPEC
        test_name = "%s_%dx%d" % testcase_spec

        if not edid.is_edid_supported(host, *testcase_spec):
            raise error.TestFail('Error: unsupported EDID: %s', test_name)

        edid_path = os.path.join(self.bindir, 'test_data', 'edids', test_name)

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

            logging.info('Use EDID: %s', test_name)
            with chameleon_port.use_edid_file(edid_path):
                index = display_facade.get_first_external_display_index()
                if not index:
                    raise error.TestFail("No external display is found.")

                resolution_list = (
                        display_facade.get_available_resolutions(index))
                logging.info('External display %d: %d resolutions found.',
                             index, len(resolution_list))

                logging.info('Set mirrored: %s', test_mirrored)
                display_facade.set_mirrored(test_mirrored)

                for r in resolution_list:
                    logging.info('Set resolution to %dx%d', *r)
                    display_facade.set_resolution(index, *r)
                    screen_test.test_screen_with_image(
                            r, test_mirrored, errors)

            if errors:
                raise error.TestFail('; '.join(set(errors)))
