# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib.cros import tpm_utils
from autotest_lib.server import test
from autotest_lib.server import autotest
from autotest_lib.server import afe_utils
from autotest_lib.server import site_utils


class enterprise_LongevityTrackerServer(test.test):
    """A test that runs enterprise_KioskEnrollment and clears the TPM as
    necessary. After enterprise enrollment is successful, it collects and logs
    cpu, memory and temperature data from the device under test."""
    version = 1

    def run_once(self, host=None, kiosk_app_attributes=None):
        self.client = host
        app_config_id = None
        tpm_utils.ClearTPMOwnerRequest(self.client)
        app_config_id = site_utils.get_label_from_afe(
                self.client.hostname, 'app_config_id', afe_utils.AFE)
        if app_config_id and app_config_id.startswith(':'):
            app_config_id = app_config_id[1:]
        autotest.Autotest(self.client).run_test('enterprise_KioskEnrollment',
                kiosk_app_attributes=kiosk_app_attributes,
                app_config_id=app_config_id,
                check_client_result=True)
        for cycle in range(5):
            autotest.Autotest(self.client).run_test('longevity_Tracker',
                    kiosk_app_attributes=kiosk_app_attributes,
                    check_client_result=True)
        tpm_utils.ClearTPMOwnerRequest(self.client)
