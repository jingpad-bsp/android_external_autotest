# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import pinweaver_client
from autotest_lib.server import test


class firmware_Cr50PinWeaverServer(test.test):
    """Tests the PinWeaver functionality on Cr50 using pinweaver_client through
    trunksd.
    """

    version = 1

    def run_once(self, host):
        """Runs the firmware_Cr50PinWeaverServer test."""
        try:
            if not pinweaver_client.SelfTest(host):
                raise error.TestFail('Failed: %s' % self.__class__.__name__)
        except pinweaver_client.PinWeaverNotAvailableError:
            logging.info('PinWeaver not supported!')
            raise error.TestNAError('PinWeaver is not available')
