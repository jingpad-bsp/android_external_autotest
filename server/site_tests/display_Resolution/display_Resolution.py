# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side resolution display test using the Chameleon board."""

import logging
import os
import time

from autotest_lib.server.cros.chameleon import chameleon_test


class display_Resolution(chameleon_test.ChameleonTest):
    """Server side external display test.

    This test talks to a Chameleon board and a DUT to set up, run, and verify
    external display function of the DUT.
    """
    version = 1
    RESOLUTION_TEST_LIST = [
            # Mix DP and HDMI together to test the converter cases.
            ('DP', 1280, 800),
            ('DP', 1440, 900),
            ('DP', 1600, 900),
            ('DP', 1680, 1050),
            ('DP', 1920, 1080),
            ('HDMI', 1280, 720),
            ('HDMI', 1920, 1080),
    ]

    def run_once(self, host, test_mirrored=False, test_suspend_resume=False,
                 test_reboot=False):
        errors = []
        for tag, width, height in self.RESOLUTION_TEST_LIST:
            test_resolution = (width, height)
            test_name = "%s_%dx%d" % ((tag,) + test_resolution)

            if not self.is_edid_supported(tag, width, height):
                logging.info('skip unsupported EDID: %s', test_name)
                continue

            self.apply_edid_file(os.path.join(
                    self.bindir, 'test_data', 'edids', test_name))

            if test_reboot:
                self.reboot()
            else:
                self.reconnect_output()
            self.set_mirrored(test_mirrored)
            if test_suspend_resume:
                if test_mirrored:
                    # magic sleep to make nyan_big wake up in mirrored mode
                    # TODO: find root cause
                    time.sleep(6)
                self.suspend_resume()

            self.load_test_image_and_check(
                    test_name, test_resolution,
                    under_mirrored_mode=test_mirrored, error_list=errors)

        self.raise_on_errors(errors)

