# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import common
from autotest_lib.client.bin import test
from autotest_lib.client.cros.cellular.mbim_compliance \
        import mbim_device_context
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_errors


class MbimTestBase(test.test):
    """
    Base class for all MBIM Compliance Suite tests.
    This class contains boilerplate code and utility functions for MBIM
    Compliance Suite. A brief description of non-trivial facilities follows.
    Test initialization: populates the following members:
        - device_context: An MBIMTestContext. This class finds the relevant MBIM
                          device on the DUT and stashes that in this context.
    Utility functions: None yet.
    """

    def run_once(self, **kwargs):
        """
        Run the test.
        @param kwargs: Optional parameters passed to device context to test
                       a specific device based on VID/PID.
                       Add id_vendor=xxxx, id_product=xxxx to the control file.

        """
        self.device_context = mbim_device_context.MbimDeviceContext(**kwargs)
        logging.info('Running test on modem with VID: %04X, PID: %04X',
                     self.device_context.id_vendor,
                     self.device_context.id_product)
        self.run_internal()


    def run_internal(self):
        """
        This method actually implements the core test logic.

        Subclasses should override this method to run their own test.

        """
        mbim_errors.log_and_raise(NotImplementedError)
