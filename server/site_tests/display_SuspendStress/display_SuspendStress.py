# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side external display test using the Chameleon board."""

import logging
import os
import random
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.chameleon import chameleon_test


class display_SuspendStress(chameleon_test.ChameleonTest):
    """Server side external display test.

    This test talks to a Chameleon board and a DUT to set up, run, and verify
    external display function of the DUT with DUT being repeatedly
    suspended and resumed.
    """
    version = 1
    DEFAULT_TESTCASE_SPEC = ('HDMI', 1920, 1080)

    # TODO: Allow reading testcase_spec from command line.
    def run_once(self, host, test_mirrored=False, testcase_spec=None,
            repeat_count=3, suspend_time_range=(5,7)):
        if testcase_spec is None:
            testcase_spec = self.DEFAULT_TESTCASE_SPEC

        test_name = "%s_%dx%d" % testcase_spec
        _, width, height = testcase_spec
        test_resolution = (width, height)

        if not self.is_edid_supported(*testcase_spec):
            raise error.TestFail('Error: EDID is not supported by the platform'
                    ': %s', test_name)

        path = os.path.join(self.bindir, 'test_data', 'edids', test_name)
        logging.info('Use EDID: %s', path)
        with self.chameleon_port.use_edid_file(path):
            # Keep the original connector name, for later comparison.
            expected_connector = (
                    self.display_facade.get_external_connector_name())
            logging.info('See the display on DUT: %s', expected_connector)

            if not expected_connector:
                raise error.TestFail('Error: Failed to see external display'
                        ' (chameleon) from DUT: %s', test_name)

            logging.info('Set mirrored: %s', test_mirrored)
            self.display_facade.set_mirrored(test_mirrored)
            logging.info('Repeat %d times Suspend and resume', repeat_count)

            while repeat_count > 0:
                repeat_count -= 1
                if test_mirrored:
                    # magic sleep to make nyan_big wake up in mirrored mode
                    # TODO: find root cause
                    time.sleep(6)
                suspend_time = random.randint(*suspend_time_range)
                logging.info('Going to suspend, for %d seconds...',
                             suspend_time)
                self.display_facade.suspend_resume(suspend_time)
                logging.info('Resumed back')

                message = self.screen_test.check_external_display_connected(
                        expected_connector)
                if not message:
                    message = self.screen_test.test_screen_with_image(
                            test_resolution, test_mirrored)
                if message:
                    raise error.TestFail(message)
