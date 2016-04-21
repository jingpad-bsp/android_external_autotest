# Copyright (c) 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib.cros import tpm_utils
from autotest_lib.server import test, autotest


class enterprise_CFM_PerfServer(test.test):
    """This is a server test which clears device TPM and runs
    enterprise_RemoraRequisition client test to enroll the device in to hotrod
    mode. After enrollment is successful, it runs the enterprise_CFM_Perf client
    test to collect and log cpu, memory and temperature data from the device
    under test."""
    version = 1


    def run_once(self, host=None):
        self.client = host

        tpm_utils.ClearTPMOwnerRequest(self.client)
        autotest.Autotest(self.client).run_test('enterprise_RemoraRequisition',
                                                check_client_result=True)

        # TODO: Start a hangout session after device enrollment succeeds.

        autotest.Autotest(self.client).run_test('enterprise_CFM_Perf',
                                                check_client_result=True)

        # TODO: End the hangout session after performance data collection is
        # done.

        tpm_utils.ClearTPMOwnerRequest(self.client)
