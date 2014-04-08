# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a setup test for the Chameleon board."""

from autotest_lib.server.cros.chameleon import chameleon_test


class display_ChameleonSetup(chameleon_test.ChameleonTest):
    """Chameleon setup test.

    This test talks to a Chameleon board and a DUT to set up. Any failure
    treats as a test fail.
    """
    version = 1

    def run_once(self):
        # The check logic is done in the super class ChameleonTest.
        pass
