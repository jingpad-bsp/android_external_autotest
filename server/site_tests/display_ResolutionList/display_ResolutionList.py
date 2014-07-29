# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side resolution display test using the Chameleon board."""

import logging # pylint: disable=W0611
import os
import random

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.chameleon import chameleon_test


class display_ResolutionList(chameleon_test.ChameleonTest):
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

        if not self.is_edid_supported(*testcase_spec):
            raise error.TestFail('Error: unsupported EDID: %s', test_name)

        self.apply_edid_file(os.path.join(
                self.bindir, 'test_data', 'edids', test_name))

        self.reconnect_output()

        display_index, resolution_list = (
                self.get_first_external_display_resolutions())
        random.shuffle(resolution_list)

        self.set_mirrored(test_mirrored)

        errors = []
        for resolution in resolution_list:
            self.set_resolution(display_index, *resolution)
            self.load_test_image_and_check(
                    test_name, resolution,
                    under_mirrored_mode = test_mirrored, error_list = errors)

        self.raise_on_errors(errors)

