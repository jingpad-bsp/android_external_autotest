# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib.cros import tpm_utils
from autotest_lib.server import test, autotest


class enterprise_CFM_VolumeChange(test.test):
    """Validate volume changes made in hotrod kiosk app against CrOS.
    """
    version = 1

    def run_once(self, host, repeat):
        self.client = host

        tpm_utils.ClearTPMOwnerRequest(self.client)

        if self.client.servo:
            self.client.servo.switch_usbkey('dut')
            self.client.servo.set('usb_mux_sel3', 'dut_sees_usbkey')
            self.client.servo.set('dut_hub1_rst1', 'off')

        autotest.Autotest(self.client).run_test(
                'enterprise_RemoraRequisition', check_client_result=True)
        autotest.Autotest(self.client).run_test(
                'enterprise_CFM_VolumeChangeClient',
                repeat=repeat,
                check_client_result=True)

        tpm_utils.ClearTPMOwnerRequest(self.client)
