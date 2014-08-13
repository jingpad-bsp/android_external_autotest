# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side external display test using the Chameleon board."""

import logging
import os
import random

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
            repeat_count=3, suspend_time_range=(1,3)):
        if testcase_spec is None:
            testcase_spec = self.DEFAULT_TESTCASE_SPEC

        test_name = "%s_%dx%d" % testcase_spec
        _, width, height = testcase_spec
        test_resolution = (width, height)

        if not self.is_edid_supported(*testcase_spec):
            raise error.TestFail('Error: EDID is not supported by the platform'
                    ': %s', test_name)
        self.apply_edid_file(os.path.join(
                self.bindir, 'test_data', 'edids', test_name))

        # Keep the original connector name, for later comparison.
        expected_connector = self.get_dut_display_connector()
        if not expected_connector:
            raise error.TestFail('Error: Failed to see external display'
                    ' (chameleon) from DUT: %s', test_name)

        self.reconnect_output()
        self.set_mirrored(test_mirrored)
        logging.info('Repeat %d times Suspend and resume', repeat_count)

        while repeat_count > 0:
            repeat_count -= 1
            self.suspend_resume(random.randint(*suspend_time_range))
            self.check_external_display_connector(expected_connector)
            error_message = self.load_test_image_and_check(
                    test_name, test_resolution,
                    under_mirrored_mode=test_mirrored)
            if error_message:
                raise error.TestFail(error_message)

